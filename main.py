from __future__ import annotations

import logging
import random
import sys
import time
import json
import os
from datetime import datetime

import config
from notify_state import NotifyState
from portal_client import LoginError, PortalClient, SessionExpiredError
from telegram_notifier import TelegramNotifier


def setup_logging():
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers = [logging.StreamHandler(sys.stdout)]
    log_file = getattr(config, "LOG_FILE", None)
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers)


log = logging.getLogger("krs_watcher.main")


def normalize_targets(targets):
    return {(k.strip().upper(), c.strip().upper()) for k, c in targets}


def load_targets_from_json(filepath="targets.json"):
    """Membaca daftar target dinamis dari file JSON yang dibuat oleh web UI."""
    if not os.path.exists(filepath):
        return set()
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
            # Konversi format dict {"kode_mk": "IF123", "kelas": "A"} ke tuple ("IF123", "A")
            targets = [(item["kode_mk"], item["kelas"]) for item in data]
            return normalize_targets(targets)
    except Exception as e:
        log.error("Gagal membaca %s: %s", filepath, e)
        return set()


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
    client: PortalClient, notifier: TelegramNotifier, state: NotifyState, targets: set
):
    courses = client.get_offered_courses()

    found_keys = set()
    for row in courses:
        key = (row["kode"].strip().upper(), row["kelas_nama"].strip().upper())
        if key not in targets:
            continue
        found_keys.add(key)

        kuota = row["sisa_kuota"]
        if kuota is None:
            log.warning(
                "Kuota tidak terbaca untuk %s %s (raw=%r)",
                row["kode"],
                row["kelas_nama"],
                row["sisa_kuota_raw"],
            )
            continue

        kode, kelas = row["kode"], row["kelas_nama"]
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


def run_watcher():
    """Fungsi utama yang akan dipanggil oleh background thread di app.py"""
    setup_logging()

    if not config.USERNAME or not config.PASSWORD:
        log.error("USERNAME / PASSWORD belum diisi di config.py")
        sys.exit(1)

    client = PortalClient(
        username=config.USERNAME,
        password=config.PASSWORD,
        timeout=getattr(config, "REQUEST_TIMEOUT_SECONDS", 30),
    )
    notifier = TelegramNotifier(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)
    state = NotifyState(getattr(config, "STATE_FILE", "notify_state.json"))

    try:
        client.ensure_logged_in()
    except LoginError as e:
        log.error("Login awal gagal: %s", e)
        sys.exit(1)

    notifier.send(
        "🚀 KRS Watcher (Web Version) mulai berjalan dan siap menerima target."
    )

    consecutive_errors = 0

    while True:
        # Load target terbaru dari web UI pada setiap iterasi
        targets = load_targets_from_json()

        if not targets:
            log.info("Belum ada matakuliah yang dipantau. Menunggu input dari web...")
        else:
            log.info("Memantau %d kelas target: %s", len(targets), sorted(targets))
            try:
                check_once(client, notifier, state, targets)
                consecutive_errors = 0
            except (LoginError, SessionExpiredError) as e:
                consecutive_errors += 1
                log.error("Masalah sesi/login (gagal ke-%d): %s", consecutive_errors, e)
            except Exception as e:
                consecutive_errors += 1
                log.exception(
                    "Error tak terduga (gagal ke-%d): %s", consecutive_errors, e
                )

            if consecutive_errors and consecutive_errors % 5 == 0:
                notifier.send(
                    f"⚠️ KRS Watcher error {consecutive_errors}x berturut-turut, cek log."
                )

        delay = random.uniform(config.POLL_MIN_SECONDS, config.POLL_MAX_SECONDS)
        log.info("Menunggu %.1f detik...", delay)
        time.sleep(delay)


if __name__ == "__main__":
    # Jika dijalankan langsung (bukan dari app.py), tetap bisa jalan
    try:
        run_watcher()
    except KeyboardInterrupt:
        log.info("Dihentikan oleh user.")
