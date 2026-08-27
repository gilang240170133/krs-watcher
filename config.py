from __future__ import annotations

import os

try:
    # Hanya dipakai saat development lokal. Di Railway, env var
    # langsung disuntikkan oleh platform jadi baris ini tidak berpengaruh.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _get(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(name, default)
    if val is not None:
        val = val.strip()
    return val or default


def _get_float(name: str, default: float) -> float:
    val = os.environ.get(name)
    try:
        return float(val) if val else default
    except ValueError:
        return default


def _get_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    try:
        return int(val) if val else default
    except ValueError:
        return default


# --- Kredensial portal & Telegram (WAJIB diisi lewat environment variable) ---
PORTAL_USERNAME = _get("PORTAL_USERNAME")
PORTAL_PASSWORD = _get("PORTAL_PASSWORD")

TELEGRAM_BOT_TOKEN = _get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _get("TELEGRAM_CHAT_ID")

# --- Pengaturan polling ---
POLL_MIN_SECONDS = _get_float("POLL_MIN_SECONDS", 30)
POLL_MAX_SECONDS = _get_float("POLL_MAX_SECONDS", 60)
REMINDER_INTERVAL_SECONDS = _get_int("REMINDER_INTERVAL_SECONDS", 120)
REQUEST_TIMEOUT_SECONDS = _get_int("REQUEST_TIMEOUT_SECONDS", 30)

# --- File penyimpanan (relatif terhadap working directory proses) ---
STATE_FILE = _get("STATE_FILE", "notify_state.json")
TARGETS_FILE = _get("TARGETS_FILE", "targets.json")
LOG_FILE = _get("LOG_FILE", "krs_watcher.log")

# --- Web UI ---
# Kalau WEB_UI_PASSWORD diisi, dashboard akan minta password sebelum bisa
# dibuka/diubah. Sangat disarankan diisi karena aplikasi ini nanti online
# dan bisa diakses siapa saja yang tahu URL-nya di Railway.
WEB_UI_PASSWORD = _get("WEB_UI_PASSWORD")
FLASK_SECRET_KEY = _get("FLASK_SECRET_KEY", "dev-secret-ganti-di-railway")


def missing_required() -> list[str]:
    """Daftar env var wajib yang belum diisi (dipakai buat proses watcher)."""
    missing = []
    if not PORTAL_USERNAME:
        missing.append("PORTAL_USERNAME")
    if not PORTAL_PASSWORD:
        missing.append("PORTAL_PASSWORD")
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_CHAT_ID:
        missing.append("TELEGRAM_CHAT_ID")
    return missing
