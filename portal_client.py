from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("krs_watcher.portal")

BASE = "http://portal.unimal.ac.id/index.php"
HOME_URL = "http://portal.unimal.ac.id/"
LOGIN_URL = f"{BASE}?pModule=zdKbnKU=&pSub=zdKbnKU=&pAct=0dWjppyl"

COURSE_LIST_LINK_TEXT = "Informasi Matakuliah Ditawarkan"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Referer": "http://portal.unimal.ac.id/index.php",
}

ENCODING = "windows-1252"


class LoginError(Exception):
    pass


class SessionExpiredError(Exception):
    pass


def _looks_like_login_form(html: str) -> bool:
    return ('id="password"' in html) and ("form-login" in html)


def _looks_like_dashboard(html: str) -> bool:
    return ("Selamat Datang" in html) or ("Kotak Pesan" in html)


def _looks_like_access_denied(html: str) -> bool:
    return "tidak diijinkan" in html.lower()


def get_soup(session: requests.Session, url: str, timeout: int = 30):
    resp = session.get(url, headers=HEADERS, timeout=timeout)
    resp.encoding = ENCODING
    return BeautifulSoup(resp.text, "html.parser"), resp


def login(session: requests.Session, username: str, password: str, timeout: int = 30):
    try:
        session.get(HOME_URL, headers=HEADERS, timeout=timeout)
    except requests.RequestException:
        pass

    resp = session.post(
        LOGIN_URL,
        data={"username": username, "password": password},
        headers={**HEADERS, "Referer": HOME_URL},
        allow_redirects=True,
        timeout=timeout,
    )
    resp.encoding = ENCODING
    text = resp.text

    success = _looks_like_dashboard(text) and not _looks_like_login_form(text)
    if not success:
        snippet = text[:300].replace("\n", " ")
        raise LoginError(
            f"Login gagal (status {resp.status_code}). Cuplikan: {snippet!r}"
        )

    log.info("Login berhasil. dashboard_url=%s", resp.url)
    return resp.url


def find_course_list_url(
    session: requests.Session, dashboard_url: str, timeout: int = 30
) -> str:
    soup, resp = get_soup(session, dashboard_url, timeout=timeout)

    for a in soup.find_all("a", href=True):
        label = a.get_text(" ", strip=True)
        if COURSE_LIST_LINK_TEXT.lower() in label.lower():
            return a["href"]

    raise SessionExpiredError(
        f"Link menu '{COURSE_LIST_LINK_TEXT}' tidak ditemukan di {dashboard_url}."
    )


def parse_course_list(soup: BeautifulSoup):
    rows_out = []

    for div in soup.find_all("div", id=re.compile(r"^semester_\d+$")):
        semester_num = div["id"].split("_")[1]

        table = div.find("table")
        if table is None:
            continue

        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 8:
                continue  # baris header

            no = tds[0].get_text(strip=True)
            kode = tds[1].get_text(strip=True)
            matakuliah = tds[2].get_text(strip=True)
            dosen = tds[3].get_text(strip=True)

            kelas_link = tds[4].find("a")
            kelas_nama = (
                kelas_link.get_text(strip=True)
                if kelas_link
                else tds[4].get_text(strip=True)
            )
            kelas_url = kelas_link["href"] if kelas_link else None

            wp = tds[5].get_text(strip=True)
            sks = tds[6].get_text(strip=True)
            sisa_kuota_raw = tds[7].get_text(strip=True)

            try:
                sisa_kuota = int(re.sub(r"[^\d\-]", "", sisa_kuota_raw) or "0")
            except ValueError:
                sisa_kuota = None

            rows_out.append(
                {
                    "semester": semester_num,
                    "no": no,
                    "kode": kode,
                    "matakuliah": matakuliah,
                    "dosen": dosen,
                    "kelas_nama": kelas_nama,
                    "kelas_url": kelas_url,
                    "wp": wp,
                    "sks": sks,
                    "sisa_kuota_raw": sisa_kuota_raw,
                    "sisa_kuota": sisa_kuota,
                }
            )

    return rows_out


@dataclass
class PortalClient:
    username: str
    password: str
    timeout: int = 30
    session: requests.Session = field(default_factory=requests.Session)
    dashboard_url: str | None = field(default=None, init=False)
    course_list_url: str | None = field(default=None, init=False)

    def ensure_logged_in(self, force: bool = False):
        if self.dashboard_url is not None and not force:
            return
        self.dashboard_url = login(
            self.session, self.username, self.password, timeout=self.timeout
        )
        self.course_list_url = find_course_list_url(
            self.session, self.dashboard_url, timeout=self.timeout
        )
        log.info("course_list_url (sesi ini): %s", self.course_list_url)

    def get_offered_courses(self, retry_on_expired: bool = True):
        self.ensure_logged_in()

        soup, resp = get_soup(self.session, self.course_list_url, timeout=self.timeout)
        courses = parse_course_list(soup)

        session_invalid = not courses and (
            _looks_like_login_form(resp.text) or _looks_like_access_denied(resp.text)
        )

        if session_invalid:
            if not retry_on_expired:
                raise SessionExpiredError(
                    "Session expired dan sudah pernah dicoba re-login."
                )
            log.warning("Session tampak expired, login ulang...")
            self.dashboard_url = None
            self.course_list_url = None
            self.ensure_logged_in(force=True)
            return self.get_offered_courses(retry_on_expired=False)

        return courses
