# KRS Watcher

Memantau kuota mata kuliah di portal kampus (Unimal) dan kirim notifikasi
Telegram begitu kuota kosong terbuka. Sekarang punya dashboard web untuk
menambah/menghapus mata kuliah yang dipantau, dan siap di-deploy ke
Railway supaya jalan 24/7 tanpa laptop nyala terus.

## Struktur

- `app.py` — Flask web app: dashboard + API + memicu background watcher.
- `watcher.py` — loop pengecekan kuota (dipakai `app.py` maupun `main.py`).
- `main.py` — jalankan watcher tanpa web UI (buat tes cepat di terminal).
- `portal_client.py` — login & scraping halaman "Informasi Matakuliah Ditawarkan".
- `telegram_notifier.py` — kirim pesan lewat Bot Telegram.
- `notify_state.py` — anti-spam notifikasi (jeda reminder per kelas).
- `targets_store.py` — penyimpanan watchlist (`targets.json`): kode, kelas, nama matkul, dosen.
- `config.py` — semua konfigurasi dibaca dari environment variable / `.env`.

## Jalan di lokal

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env, isi PORTAL_USERNAME, PORTAL_PASSWORD, TELEGRAM_BOT_TOKEN,
# TELEGRAM_CHAT_ID, WEB_UI_PASSWORD

python app.py
```

Buka `http://localhost:5000`, masukkan `WEB_UI_PASSWORD`, lalu:

1. Klik **"Ambil daftar dari portal"** untuk melihat mata kuliah yang
   sedang ditawarkan (nama, kode, kelas, dosen, sisa kuota).
2. Cari mata kuliah lewat kotak pencarian, klik **"+ Pantau"** untuk
   menambahkannya ke watchlist.
3. Watcher berjalan otomatis di background begitu app dijalankan, dan
   akan langsung membaca perubahan watchlist tanpa perlu restart.

Kalau cuma mau jalanin watcher-nya saja tanpa dashboard (mis. watchlist
sudah pernah diisi lewat web dan filenya masih ada), pakai `python main.py`.

## Deploy ke Railway

1. Push folder ini ke sebuah repo GitHub (file `.env` **tidak** ikut ter-push
   karena sudah masuk `.gitignore` — memang harus begitu).
2. Di Railway: **New Project → Deploy from GitHub repo**, pilih repo ini.
   Railway otomatis mendeteksi `Procfile` dan `requirements.txt`.
3. Buka tab **Variables**, isi:
   - `PORTAL_USERNAME`, `PORTAL_PASSWORD`
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
   - `WEB_UI_PASSWORD` (password untuk buka dashboard)
   - `FLASK_SECRET_KEY` (string acak, buat sesi login aman)
4. Deploy. Railway kasih domain publik (`*.up.railway.app`) — itu alamat
   dashboard kamu.
5. Buka domain tsb, login, lalu tambahkan mata kuliah yang mau dipantau.

### Catatan penting soal penyimpanan di Railway

`targets.json` dan `notify_state.json` disimpan sebagai file biasa di
filesystem container. Selama container tidak di-redeploy/restart, datanya
aman. **Tapi setiap kali kamu redeploy (push commit baru), Railway bikin
container baru dan file-file itu ikut hilang** — watchlist akan kosong
lagi. Kalau ini mengganggu, tambahkan **Railway Volume** dan mount ke
folder project ini (lalu arahkan `TARGETS_FILE`/`STATE_FILE` ke path di
volume tsb lewat environment variable) supaya datanya persist antar
deploy.

### Kenapa cuma 1 worker gunicorn?

`Procfile` sengaja pakai `--workers 1`. Watcher jalan sebagai satu
background thread di dalam proses web; kalau workernya lebih dari satu,
loop pengecekan bakal jalan dobel/tripel dan notifikasi Telegram bisa
terkirim berkali-kali untuk kejadian yang sama. `--threads 4` sudah
cukup buat menangani beberapa request dashboard sekaligus karena
trafiknya ringan (cuma kamu yang pakai).

## Environment variables

Lihat `.env.example` untuk daftar lengkap beserta penjelasan singkat.
