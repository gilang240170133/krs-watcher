from __future__ import annotations

import json
import logging
import os
import threading
import time

log = logging.getLogger("krs_watcher.state")

_lock = threading.RLock()


class NotifyState:
    def __init__(self, path: str):
        self.path = path
        self._last_notified: dict[str, float] = {}
        self._load()

    def _key(self, kode: str, kelas: str) -> str:
        return f"{kode.strip().upper()}|{kelas.strip().upper()}"

    def _load(self):
        with _lock:
            if os.path.exists(self.path):
                try:
                    with open(self.path, "r", encoding="utf-8") as f:
                        self._last_notified = json.load(f)
                except (json.JSONDecodeError, OSError) as e:
                    log.warning(
                        "Gagal baca state file %s (%s), mulai kosong.", self.path, e
                    )
                    self._last_notified = {}

    def _save(self):
        with _lock:
            try:
                with open(self.path, "w", encoding="utf-8") as f:
                    json.dump(self._last_notified, f, indent=2)
            except OSError as e:
                log.warning("Gagal simpan state file %s: %s", self.path, e)

    def should_notify(
        self, kode: str, kelas: str, reminder_interval_seconds: int
    ) -> bool:
        with _lock:
            key = self._key(kode, kelas)
            last = self._last_notified.get(key)
            if last is None:
                return True
            return (time.time() - last) >= reminder_interval_seconds

    def mark_notified(self, kode: str, kelas: str):
        with _lock:
            key = self._key(kode, kelas)
            self._last_notified[key] = time.time()
            self._save()

    def reset(self, kode: str, kelas: str):
        with _lock:
            key = self._key(kode, kelas)
            if key in self._last_notified:
                del self._last_notified[key]
                self._save()
