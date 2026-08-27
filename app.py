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


@app.route("/api/courses")
@login_required
def api_courses():
    """Ambil daftar mata kuliah yang sedang ditawarkan langsung dari portal.

    Dipakai untuk mengisi daftar pilihan "tambah mata kuliah" di dashboard,
    supaya yang tampil bukan cuma kode tapi juga nama matkul & dosennya.
    """
    missing = config.missing_required()
    if "PORTAL_USERNAME" in missing or "PORTAL_PASSWORD" in missing:
        return (
            jsonify({"error": "PORTAL_USERNAME / PORTAL_PASSWORD belum diisi di environment"}),
            400,
        )

    try:
        client = PortalClient(
            username=config.PORTAL_USERNAME,
            password=config.PORTAL_PASSWORD,
            timeout=config.REQUEST_TIMEOUT_SECONDS,
        )
        client.ensure_logged_in()
        courses = client.get_offered_courses()
    except (LoginError, SessionExpiredError) as e:
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        log.exception("Gagal ambil daftar matkul dari portal")
        return jsonify({"error": str(e)}), 500

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
            }
            for c in courses
        ]
    )


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
