from flask import Flask, request, render_template_string, redirect, url_for
import threading
import json
import os
import time
from main import run_watcher

app = Flask(__name__)

# Tampilan Web dengan Tabel dan CSS tambahan
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KRS Watcher</title>
    <style>
        body { font-family: sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; }
        input, button { padding: 10px; margin: 5px 0; width: 100%; box-sizing: border-box; }
        .btn-primary { background-color: #007bff; color: white; border: none; cursor: pointer; font-weight: bold; }
        .btn-danger { background-color: #dc3545; color: white; border: none; cursor: pointer; padding: 6px 12px; text-decoration: none; display: inline-block; border-radius: 4px; font-size: 14px;}
        table { width: 100%; border-collapse: collapse; margin-top: 25px; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
        th { background-color: #f8f9fa; }
        .alert { color: green; font-weight: bold; }
        .alert-error { color: red; font-weight: bold; }
    </style>
</head>
<body>
    <h2>Target Pantauan KRS</h2>
    
    <form action="/" method="POST">
        <input type="text" name="kode_mk" placeholder="Kode Matakuliah (contoh: IF123)" required>
        <input type="text" name="kelas" placeholder="Kelas (contoh: A)" required>
        <button type="submit" class="btn-primary">Tambah Pantauan</button>
    </form>
    
    {% if message %}
    <p class="alert">{{ message }}</p>
    {% endif %}

    <h3>Daftar Pantauan Saat Ini</h3>
    <table>
        <thead>
            <tr>
                <th>Kode MK</th>
                <th>Kelas</th>
                <th>Aksi</th>
            </tr>
        </thead>
        <tbody>
            {% for target in targets %}
            <tr>
                <td><strong>{{ target.kode_mk }}</strong></td>
                <td>{{ target.kelas }}</td>
                <td style="text-align: center;">
                    <a href="/delete/{{ target.kode_mk }}/{{ target.kelas }}" class="btn-danger" onclick="return confirm('Yakin ingin menghapus kelas ini?')">Hapus</a>
                </td>
            </tr>
            {% else %}
            <tr>
                <td colspan="3" style="text-align: center; color: #666;">Belum ada matakuliah yang dipantau.</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""

def load_targets():
    """Fungsi pembantu untuk membaca JSON."""
    if os.path.exists('targets.json'):
        try:
            with open('targets.json', 'r') as f:
                return json.load(f)
        except:
            pass
    return []

def save_targets(targets):
    """Fungsi pembantu untuk menyimpan ke JSON."""
    with open('targets.json', 'w') as f:
        json.dump(targets, f)

@app.route('/', methods=['GET', 'POST'])
def index():
    message = ""
    targets = load_targets()
    
    if request.method == 'POST':
        # Mengubah input menjadi huruf besar semua agar seragam
        kode_mk = request.form['kode_mk'].strip().upper()
        kelas = request.form['kelas'].strip().upper()
        
        # Mencegah duplikasi data
        if not any(t['kode_mk'] == kode_mk and t['kelas'] == kelas for t in targets):
            targets.append({"kode_mk": kode_mk, "kelas": kelas})
            save_targets(targets)
            message = f"Berhasil menambahkan: {kode_mk} (Kelas {kelas})"
        else:
            message = f"Matakuliah {kode_mk} (Kelas {kelas}) sudah ada di daftar!"
            
    return render_template_string(HTML_TEMPLATE, message=message, targets=targets)

@app.route('/delete/<kode_mk>/<kelas>')
def delete(kode_mk, kelas):
    targets = load_targets()
    # Memfilter list, membuang item yang cocok dengan parameter URL
    targets = [t for t in targets if not (t['kode_mk'] == kode_mk and t['kelas'] == kelas)]
    save_targets(targets)
    return redirect(url_for('index'))

@app.route('/ping')
def ping():
    return "OK", 200

if __name__ == '__main__':
    watcher_thread = threading.Thread(target=run_watcher, daemon=True)
    watcher_thread.start()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
