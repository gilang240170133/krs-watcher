from __future__ import annotations

import logging
import os
import sys
import threading
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

import config
import watcher
from portal_client import LoginError, PortalClient, SessionExpiredError
from settings_store import SettingsStore
from targets_store import TargetsStore


def setup_logging():
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers = [logging.StreamHandler(sys.stdout)]
    if config.LOG_FILE:
        handlers.append(logging.FileHandler(config.LOG_FILE, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers)


setup_logging()
log = logging.getLogger("krs_watcher.app")

app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY

store = TargetsStore(config.TARGETS_FILE)
settings_store = SettingsStore(config.SETTINGS_FILE)

# --- Client portal yang dipakai bareng oleh /api/courses & /api/courses/schedule ---
# Sengaja dibuat satu instance yang dipakai ulang (bukan bikin baru tiap
# request) supaya sesi login tidak perlu diulang tiap kali mau ambil jadwal
# satu-satu per kelas -- kalau tiap request login ulang, bisa lambat dan
# berisiko portalnya nge-block gara-gara login beruntun.
_portal_client: PortalClient | None = None
_portal_client_lock = threading.Lock()


def get_portal_client() -> PortalClient:
    global _portal_client
    with _portal_client_lock:
        if _portal_client is None:
            _portal_client = PortalClient(
                username=config.PORTAL_USERNAME,
                password=config.PORTAL_PASSWORD,
                timeout=config.REQUEST_TIMEOUT_SECONDS,
            )
        return _portal_client


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if config.WEB_UI_PASSWORD and not session.get("authed"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if not config.WEB_UI_PASSWORD:
        # Belum ada password diset -> jangan blokir siapa pun, langsung masuk.
        session["authed"] = True
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        pw = request.form.get("password", "")
        if pw == config.WEB_UI_PASSWORD:
            session["authed"] = True
            nxt = request.args.get("next") or url_for("index")
            return redirect(nxt)
        error = "Password salah."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.pop("authed", None)
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template(
        "index.html",
        targets=store.list(),
        missing_env=config.missing_required(),
        web_ui_protected=bool(config.WEB_UI_PASSWORD),
    )


@app.route("/api/status")
@login_required
def api_status():
    return jsonify({**watcher.status.snapshot(), "missing_env": config.missing_required()})


@app.route("/api/targets", methods=["GET"])
@login_required
def api_targets_list():
    return jsonify(store.list())


@app.route("/api/targets", methods=["POST"])
@login_required
def api_targets_add():
    data = request.get_json(force=True, silent=True) or {}
    kode = (data.get("kode") or "").strip()
    kelas_nama = (data.get("kelas_nama") or "").strip()
    matakuliah = (data.get("matakuliah") or "").strip()
    dosen = (data.get("dosen") or "").strip()
    if not kode or not kelas_nama:
        return jsonify({"error": "kode dan kelas_nama wajib diisi"}), 400
    t = store.add(kode, kelas_nama, matakuliah=matakuliah, dosen=dosen)
    return jsonify(t), 201


@app.route("/api/targets", methods=["DELETE"])
@login_required
def api_targets_remove():
    data = request.get_json(force=True, silent=True) or {}
    kode = (data.get("kode") or "").strip()
    kelas_nama = (data.get("kelas_nama") or "").strip()
    if not kode or not kelas_nama:
        return jsonify({"error": "kode dan kelas_nama wajib diisi"}), 400
    changed = store.remove(kode, kelas_nama)
    return jsonify({"removed": changed})


@app.route("/api/settings", methods=["GET"])
@login_required
def api_settings_get():
    return jsonify(settings_store.get())


@app.route("/api/settings", methods=["POST"])
@login_required
def api_settings_set():
    """Simpan filter semester (mata kuliah semester berapa saja yang mau
    ditampilkan waktu "Ambil daftar dari portal"). Kirim list kosong untuk
    kembali menampilkan semua semester.
    """
    data = request.get_json(force=True, silent=True) or {}
    semesters = data.get("semesters")
    if semesters is None or not isinstance(semesters, list):
        return jsonify({"error": "field 'semesters' wajib berupa list"}), 400
    saved = settings_store.set_semesters(semesters)
    return jsonify(saved)


@app.route("/api/courses")
@login_required
def api_courses():
    """Ambil daftar mata kuliah yang sedang ditawarkan langsung dari portal.

    Dipakai untuk mengisi daftar pilihan "tambah mata kuliah" di dashboard,
    supaya yang tampil bukan cuma kode tapi juga nama matkul & dosennya.
    Hasilnya difilter sesuai pengaturan semester yang tersimpan (kalau ada
    yang dipilih) -- kosong berarti tampilkan semua semester.
    """
    missing = config.missing_required()
    if "PORTAL_USERNAME" in missing or "PORTAL_PASSWORD" in missing:
        return (
            jsonify({"error": "PORTAL_USERNAME / PORTAL_PASSWORD belum diisi di environment"}),
            400,
        )

    try:
        client = get_portal_client()
        client.ensure_logged_in()
        courses = client.get_offered_courses()
    except (LoginError, SessionExpiredError) as e:
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        log.exception("Gagal ambil daftar matkul dari portal")
        return jsonify({"error": str(e)}), 500

    selected_semesters = set(settings_store.get_semesters())
    if selected_semesters:
        courses = [c for c in courses if str(c["semester"]).strip() in selected_semesters]

    return jsonify(
        [
            {
                "kode": c["kode"],
                "kelas_nama": c["kelas_nama"],
                "matakuliah": c["matakuliah"],
                "dosen": c["dosen"],
                "wp": c["wp"],
                "sks": c["sks"],
                "sisa_kuota": c["sisa_kuota"],
                "semester": c["semester"],
                "kelas_url": c.get("kelas_url"),
            }
            for c in courses
        ]
    )


@app.route("/api/courses/schedule")
@login_required
def api_course_schedule():
    """Ambil jadwal (hari/jam/ruang) satu kelas, dipanggil satu-satu dari
    dashboard sesudah daftar mata kuliah berhasil ditampilkan.

    Dibuat toleran: kalau kelasnya memang belum ada jadwal di portal, atau
    halamannya gagal di-parse, balikin jadwal null (bukan error) supaya
    tampilan depan tidak crash -- cukup tampilkan "jadwal belum tersedia".
    """
    kelas_url = (request.args.get("kelas_url") or "").strip()
    if not kelas_url:
        return jsonify({"error": "kelas_url wajib diisi"}), 400

    missing = config.missing_required()
    if "PORTAL_USERNAME" in missing or "PORTAL_PASSWORD" in missing:
        return (
            jsonify({"error": "PORTAL_USERNAME / PORTAL_PASSWORD belum diisi di environment"}),
            400,
        )

    try:
        client = get_portal_client()
        jadwal = client.get_class_schedule(kelas_url)
    except (LoginError, SessionExpiredError) as e:
        return jsonify({"error": str(e)}), 502
    except Exception:
        log.exception("Gagal ambil jadwal kelas (kelas_url=%s), anggap tidak tersedia.", kelas_url)
        jadwal = None

    return jsonify({"kelas_url": kelas_url, "jadwal": jadwal})


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True})


# --- Jalankan loop watcher di background thread, sekali per proses ---
_watcher_started = False
_watcher_lock = threading.Lock()


def ensure_watcher_started():
    global _watcher_started
    with _watcher_lock:
        if _watcher_started:
            return
        # Hindari start dobel gara-gara auto-reloader Flask waktu development.
        if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
            return
        watcher.start_background_thread()
        _watcher_started = True
        log.info("Background watcher thread dimulai.")


ensure_watcher_started()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
