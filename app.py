from flask import Flask, request, render_template_string
import threading
import json
import os
import time

from main import run_watcher

app = Flask(__name__)

# Tampilan Web Minimalis (HTML)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KRS Watcher</title>
    <style>
        body { font-family: sans-serif; max-width: 500px; margin: 40px auto; padding: 20px; }
        input, button { padding: 10px; margin: 5px 0; width: 100%; box-sizing: border-box; }
        button { background-color: #007bff; color: white; border: none; cursor: pointer; }
    </style>
</head>
<body>
    <h2>Target Pantauan KRS</h2>
    <form method="POST">
        <input type="text" name="kode_mk" placeholder="Kode Matakuliah (contoh: IF123)" required>
        <input type="text" name="kelas" placeholder="Kelas (contoh: A)" required>
        <button type="submit">Tambah Pantauan</button>
    </form>
    <p style="color: green;"><b>{{ message }}</b></p>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    message = ""
    if request.method == 'POST':
        kode_mk = request.form['kode_mk']
        kelas = request.form['kelas']

        # Menyimpan target ke file JSON agar bisa dibaca oleh watcher
        targets = []
        if os.path.exists('targets.json'):
            with open('targets.json', 'r') as f:
                try:
                    targets = json.load(f)
                except:
                    pass

        targets.append({"kode_mk": kode_mk, "kelas": kelas})
        with open('targets.json', 'w') as f:
            json.dump(targets, f)

        message = f"Berhasil menambahkan: {kode_mk} (Kelas {kelas})"

    return render_template_string(HTML_TEMPLATE, message=message)

# Route ini sangat penting untuk Cron Job (Anti-Sleep)
@app.route('/ping')
def ping():
    return "OK", 200

def run_background_watcher():
    """
    Di sini kamu meletakkan logika perulangan (while True) dari main.py milikmu.
    Modifikasi main.py agar membaca target dari file 'targets.json' di atas.
    """
    print("Background watcher berjalan...")
    # Contoh pemanggilan:
    # while True:
    #     cek_krs_dari_json()
    #     time.sleep(60)


if __name__ == '__main__':
    watcher_thread = threading.Thread(target=run_watcher, daemon=True)
    watcher_thread.start()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)