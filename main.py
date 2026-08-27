"""Jalankan watcher saja lewat CLI, tanpa web UI.

Berguna untuk tes lokal. Watchlist tetap dibaca/ditulis dari file yang
sama (targets.json) dengan yang dipakai dashboard web, jadi kalau
dashboard-nya juga jalan (mis. lewat `python app.py` di terminal lain),
keduanya akan saling sinkron lewat file itu.
"""

from __future__ import annotations

import logging
import sys

import config
from watcher import run_forever


def setup_logging():
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers = [logging.StreamHandler(sys.stdout)]
    if config.LOG_FILE:
        handlers.append(logging.FileHandler(config.LOG_FILE, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers)


if __name__ == "__main__":
    setup_logging()
    log = logging.getLogger("krs_watcher.main")
    try:
        run_forever()
    except KeyboardInterrupt:
        log.info("Dihentikan oleh user.")
