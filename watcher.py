from __future__ import annotations

import logging
import random
import threading
import time
from datetime import datetime

import config
from notify_state import NotifyState
from portal_client import LoginError, PortalClient, SessionExpiredError
from targets_store import TargetsStore
from telegram_notifier import TelegramNotifier

log = logging.getLogger("krs_watcher.watcher")


class WatcherStatus:
    """Status singkat yang dibaca dashboard web (thread-safe)."""

    def __init__(self):
        self._lock = threading.RLock()
        self.running = False
        self.last_check_at: str | None = None
        self.last_error: str | None = None
        self.last_courses_seen: int = 0

    def update(self, **kwargs):
        with self._lock:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "running": self.running,
                "last_check_at": self.last_check_at,
                "last_error": self.last_error,
                "last_courses_seen": self.last_courses_seen,
            }


status = WatcherStatus()


def format_notification(row: dict) -> str:
    return (
        f"🎉 <b>Kuota tersedia!</b>\n"
        f"Mata Kuliah: <b>{row['matakuliah']}</b> ({row['kode']})\n"
        f"Kelas: <b>{row['kelas_nama']}</b>\n"
        f"Dosen: {row['dosen']}\n"
        f"Sisa Kuota: <b>{row['sisa_kuota']}</b>\n"
        f"SKS: {row['sks']} | W/P: {row['wp']}\n"
        f"Semester: {row['semester']}\n"
        f"Waktu cek: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )


def check_once(
    client: PortalClient,
    notifier: TelegramNotifier,
    state: NotifyState,
    store: TargetsStore,
):
    targets = store.as_key_set()
    if not targets:
        log.info("Belum ada mata kuliah yang dipantau, lewati pengecekan.")
        status.update(last_courses_seen=0)
        return

    courses = client.get_offered_courses()
    status.update(last_courses_seen=len(courses))

    found_keys = set()
    for row in courses:
        key = (row["kode"].strip().upper(), row["kelas_nama"].strip().upper())
        if key not in targets:
            continue
        found_keys.add(key)

        kode, kelas = row["kode"], row["kelas_nama"]
        kuota = row["sisa_kuota"]

        # Simpan/segarkan nama matkul & dosen di watchlist supaya tampilan
        # web selalu punya nama yang manusiawi, bukan cuma kode.
        store.add(kode, kelas, matakuliah=row["matakuliah"], dosen=row["dosen"])

        if kuota is None:
            log.warning(
                "Kuota tidak terbaca untuk %s %s (raw=%r)",
                kode,
                kelas,
                row["sisa_kuota_raw"],
            )
            continue

        if kuota > 0:
            if state.should_notify(kode, kelas, config.REMINDER_INTERVAL_SECONDS):
                log.info(
                    "Kuota tersedia: %s %s = %s -> kirim notif", kode, kelas, kuota
                )
                if notifier.send(format_notification(row)):
                    state.mark_notified(kode, kelas)
            else:
                log.info(
                    "Kuota tersedia: %s %s = %s (dalam jeda reminder)",
                    kode,
                    kelas,
                    kuota,
                )
        else:
            state.reset(kode, kelas)
            log.info("Kuota %s %s = %s", kode, kelas, kuota)

    for kode, kelas in targets - found_keys:
        log.warning("Kelas target %s %s tidak ditemukan di halaman portal", kode, kelas)


def run_forever(stop_event: threading.Event | None = None):
    missing = config.missing_required()
    if missing:
        msg = f"Konfigurasi belum lengkap, env berikut kosong: {', '.join(missing)}"
        log.error(msg)
        status.update(running=False, last_error=msg)
        return

    client = PortalClient(
        username=config.PORTAL_USERNAME,
        password=config.PORTAL_PASSWORD,
        timeout=config.REQUEST_TIMEOUT_SECONDS,
    )
    notifier = TelegramNotifier(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)
    state = NotifyState(config.STATE_FILE)
    store = TargetsStore(config.TARGETS_FILE)

    try:
        client.ensure_logged_in()
    except LoginError as e:
        log.error("Login awal gagal: %s", e)
        status.update(running=False, last_error=f"Login awal gagal: {e}")
        return

    status.update(running=True, last_error=None)
    notifier.send("🚀 KRS Watcher mulai berjalan (online di Railway).")

    consecutive_errors = 0
    while stop_event is None or not stop_event.is_set():
        try:
            check_once(client, notifier, state, store)
            consecutive_errors = 0
            status.update(
                last_check_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                last_error=None,
            )
        except (LoginError, SessionExpiredError) as e:
            consecutive_errors += 1
            log.error("Masalah sesi/login (gagal ke-%d): %s", consecutive_errors, e)
            status.update(last_error=str(e))
        except Exception as e:
            consecutive_errors += 1
            log.exception("Error tak terduga (gagal ke-%d): %s", consecutive_errors, e)
            status.update(last_error=str(e))

        if consecutive_errors and consecutive_errors % 5 == 0:
            notifier.send(
                f"⚠️ KRS Watcher error {consecutive_errors}x berturut-turut, cek log."
            )

        delay = random.uniform(config.POLL_MIN_SECONDS, config.POLL_MAX_SECONDS)
        log.info("Menunggu %.1f detik...", delay)
        if stop_event is not None:
            stop_event.wait(delay)
        else:
            time.sleep(delay)

    status.update(running=False)


def start_background_thread() -> threading.Thread:
    """Dipanggil sekali oleh app.py saat proses web dijalankan."""
    t = threading.Thread(target=run_forever, name="krs-watcher-loop", daemon=True)
    t.start()
    return t
