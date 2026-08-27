from __future__ import annotations

import json
import logging
import os
import threading

log = logging.getLogger("krs_watcher.settings")

_lock = threading.RLock()

DEFAULT_SETTINGS = {
    # Daftar semester (string) yang mau ditampilkan waktu "Ambil daftar dari
    # portal". Kosong = tampilkan semua semester (tidak difilter).
    "semesters": [],
}


class SettingsStore:
    """Penyimpanan pengaturan sederhana (saat ini cuma filter semester).

    Disimpan sebagai JSON kecil di filesystem, mirip pola TargetsStore,
    supaya pilihan semester tidak hilang tiap kali halaman di-refresh.
    """

    def __init__(self, path: str):
        self.path = path
        self._settings: dict = dict(DEFAULT_SETTINGS)
        self._load()

    def _load(self):
        with _lock:
            if os.path.exists(self.path):
                try:
                    with open(self.path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        self._settings = {**DEFAULT_SETTINGS, **data}
                except (json.JSONDecodeError, OSError) as e:
                    log.warning("Gagal baca %s (%s), pakai default.", self.path, e)
                    self._settings = dict(DEFAULT_SETTINGS)
            else:
                self._settings = dict(DEFAULT_SETTINGS)

    def _save_locked(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2, ensure_ascii=False)
        except OSError as e:
            log.warning("Gagal simpan %s: %s", self.path, e)

    def get(self) -> dict:
        with _lock:
            return dict(self._settings)

    def get_semesters(self) -> list[str]:
        """Balikin daftar semester (string) yang dipilih, sudah dibersihkan."""
        with _lock:
            raw = self._settings.get("semesters") or []
        cleaned = []
        for s in raw:
            s = str(s).strip()
            if s and s not in cleaned:
                cleaned.append(s)
        return cleaned

    def set_semesters(self, semesters: list) -> dict:
        cleaned = []
        for s in semesters or []:
            s = str(s).strip()
            if s and s not in cleaned:
                cleaned.append(s)
        with _lock:
            self._settings["semesters"] = cleaned
            self._save_locked()
            return dict(self._settings)
