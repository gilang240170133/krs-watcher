from __future__ import annotations

import json
import logging
import os
import threading

log = logging.getLogger("krs_watcher.targets")

_lock = threading.RLock()


class TargetsStore:
    """Menyimpan daftar mata kuliah yang dipantau (kode + kelas + nama).

    Nama mata kuliah ikut disimpan supaya tampilan web tidak cuma
    menampilkan kode/kelas mentah -- biar gak bingung pas nambahin atau
    ngecek daftar pantauan.
    """

    def __init__(self, path: str):
        self.path = path
        self._targets: list[dict] = []
        self._load()

    def _load(self):
        with _lock:
            if os.path.exists(self.path):
                try:
                    with open(self.path, "r", encoding="utf-8") as f:
                        self._targets = json.load(f)
                except (json.JSONDecodeError, OSError) as e:
                    log.warning("Gagal baca %s (%s), mulai kosong.", self.path, e)
                    self._targets = []
            else:
                self._targets = []

    def _save_locked(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._targets, f, indent=2, ensure_ascii=False)
        except OSError as e:
            log.warning("Gagal simpan %s: %s", self.path, e)

    def list(self) -> list[dict]:
        with _lock:
            return [dict(t) for t in self._targets]

    def add(self, kode: str, kelas_nama: str, matakuliah: str = "", dosen: str = "") -> dict:
        kode = kode.strip().upper()
        kelas_nama = kelas_nama.strip().upper()
        matakuliah = matakuliah.strip()
        dosen = dosen.strip()

        with _lock:
            for t in self._targets:
                if t["kode"] == kode and t["kelas_nama"] == kelas_nama:
                    if matakuliah:
                        t["matakuliah"] = matakuliah
                    if dosen:
                        t["dosen"] = dosen
                    self._save_locked()
                    return dict(t)

            new_t = {
                "kode": kode,
                "kelas_nama": kelas_nama,
                "matakuliah": matakuliah,
                "dosen": dosen,
            }
            self._targets.append(new_t)
            self._save_locked()
            return dict(new_t)

    def remove(self, kode: str, kelas_nama: str) -> bool:
        kode = kode.strip().upper()
        kelas_nama = kelas_nama.strip().upper()
        with _lock:
            before = len(self._targets)
            self._targets = [
                t
                for t in self._targets
                if not (t["kode"] == kode and t["kelas_nama"] == kelas_nama)
            ]
            changed = len(self._targets) != before
            if changed:
                self._save_locked()
            return changed

    def as_key_set(self) -> set[tuple[str, str]]:
        with _lock:
            return {(t["kode"], t["kelas_nama"]) for t in self._targets}
