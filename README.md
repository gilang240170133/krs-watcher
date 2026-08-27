# KRS Watcher — Notifikasi Kuota Kelas via Telegram

Memantau kolom **Sisa Kuota** di halaman *Informasi Matakuliah Ditawarkan*
portal.unimal.ac.id secara berkala, dan mengirim notifikasi Telegram begitu
kuota kelas yang kamu incar berubah dari 0 menjadi tersedia — cocok untuk
"war KRS".

## Struktur file

```
krs_watcher/
├── config.py            # kredensial, token telegram, kelas target
├── portal_client.py     # login & scraping portal
├── telegram_notifier.py # kirim pesan ke Telegram
├── notify_state.py      # anti-spam notifikasi
├── main.py               # program utama (loop polling)
└── requirements.txt
```

## Cara kerja `portal_client.py`

- Kode `pModule`/`pSub` pada URL menu "Informasi Matakuliah Ditawarkan"
  **terikat per-sesi login**, tidak bisa di-hardcode. Setelah login,
  `find_course_list_url()` mencari ulang link menu itu dari halaman
  dashboard hasil redirect login (`dashboard_url`) — bukan dari `/` biasa,
  karena `/` belum tentu menampilkan konten yang sudah authenticated.
- Session (`PHPSESSID`) bisa timeout/expired kapan saja. `PortalClient.get_offered_courses()`
  mendeteksi tanda-tanda session tidak valid lagi (balik ke form login, atau
  pesan "tidak diijinkan mengakses module"), lalu otomatis login ulang dan
  mencoba sekali lagi — tanpa perlu restart script manual.
- Kolom **Sisa Kuota** sudah tersedia langsung di tabel daftar mata kuliah,
  jadi tidak perlu membuka halaman detail tiap kelas satu-satu — sekali
  fetch per polling saja.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Buat Bot Telegram

1. Chat `@BotFather` di Telegram → `/newbot` → ikuti instruksi → dapat
   **token** (formatnya seperti `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`).
2. Chat bot kamu sendiri (klik nama bot, lalu `/start`) — kalau tidak
   dimulai duluan, bot tidak bisa kirim pesan ke kamu.
3. Buka `https://api.telegram.org/bot<TOKEN>/getUpdates` (ganti `<TOKEN>`),
   cari `"chat":{"id": ...}` — itu **chat_id** kamu.

## Isi `config.py`

| Variabel | Keterangan |
|---|---|
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | dari langkah di atas |
| `USERNAME`, `PASSWORD` | kredensial portal |
| `TARGET_CLASSES` | list `(KODE, KELAS)`, harus sama persis dengan kolom **Kode** dan **Kelas** di halaman Informasi Matakuliah Ditawarkan (tidak case-sensitive, spasi ujung otomatis dibuang) |
| `POLL_MIN_SECONDS` / `POLL_MAX_SECONDS` | jeda acak antar-cek, supaya traffic ke portal tidak terlalu sering/predictable |
| `REMINDER_INTERVAL_SECONDS` | selama kuota masih > 0, tidak di-notif tiap siklus polling — cukup diingatkan ulang tiap interval ini |
| `REQUEST_TIMEOUT_SECONDS` | timeout HTTP request (detik) |
| `STATE_FILE` | file JSON penyimpan histori notifikasi terakhir (anti-spam saat restart) |
| `LOG_FILE` | file log aktivitas (selain tampil di terminal) |

## Jalankan

```bash
python main.py
```

Urutan yang terjadi:
1. Login ke portal.
2. Cari otomatis URL menu "Informasi Matakuliah Ditawarkan" untuk sesi aktif.
3. Kirim pesan Telegram "🚀 KRS Watcher mulai berjalan" sebagai tanda semua tersambung.
4. Polling berulang dengan jeda acak; kirim notif begitu kelas target kuotanya > 0.
5. Kalau session expired di tengah jalan, login ulang otomatis.

Hentikan dengan `Ctrl+C`.

## Menjalankan terus-menerus (opsional)

Supaya tetap jalan meski terminal ditutup: `tmux`/`screen`, `nohup python main.py &`,
atau jadikan systemd service / scheduled task.

## ⚠️ Keamanan

- `config.py` menyimpan password portal & token Telegram dalam bentuk
  plaintext. Jangan commit ke Git publik atau bagikan ke orang lain
  (`.gitignore` sudah menyertakan file ini secara default).
- Jangan bagikan file HAR/log yang berisi request login (mengandung password
  plaintext) ke siapa pun, termasuk AI assistant — redact dulu kalau perlu.
- Gunakan interval polling yang wajar (default 30–60 detik), jangan
  dipercepat drastis supaya tidak membebani server portal kampus.
