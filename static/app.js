(function () {
  "use strict";

  const pulseDot = document.getElementById("pulseDot");
  const statusText = document.getElementById("statusText");
  const watchedList = document.getElementById("watchedList");
  const watchedCount = document.getElementById("watchedCount");
  const courseList = document.getElementById("courseList");
  const courseEmpty = document.getElementById("courseEmpty");
  const courseFilter = document.getElementById("courseFilter");
  const btnLoadCourses = document.getElementById("btnLoadCourses");

  let watchedKeys = new Set(
    Array.from(watchedList.querySelectorAll(".row")).map(
      (r) => r.dataset.kode + "|" + r.dataset.kelas
    )
  );
  let lastCourses = [];

  function keyOf(kode, kelas) {
    return kode.trim().toUpperCase() + "|" + kelas.trim().toUpperCase();
  }

  function fmtTime(iso) {
    return iso || "-";
  }

  async function refreshStatus() {
    try {
      const res = await fetch("/api/status");
      const s = await res.json();

      if (s.missing_env && s.missing_env.length) {
        pulseDot.className = "pulse-dot err";
        statusText.textContent = "Konfigurasi belum lengkap";
        return;
      }
      if (s.last_error) {
        pulseDot.className = "pulse-dot err";
        statusText.textContent = "Error: " + s.last_error;
        return;
      }
      if (s.running) {
        pulseDot.className = "pulse-dot on";
        statusText.textContent = s.last_check_at
          ? "Online \u00b7 cek terakhir " + fmtTime(s.last_check_at)
          : "Online \u00b7 menunggu cek pertama";
      } else {
        pulseDot.className = "pulse-dot";
        statusText.textContent = "Watcher belum berjalan";
      }
    } catch (e) {
      pulseDot.className = "pulse-dot err";
      statusText.textContent = "Tidak bisa menghubungi server";
    }
  }

  function quotaBoxHtml(sisa) {
    if (sisa === null || sisa === undefined) {
      return '<div class="quota" title="Kuota belum dicek">&mdash;</div>';
    }
    const cls = sisa > 0 ? "quota open" : "quota";
    return '<div class="' + cls + '" title="Sisa kuota">' + sisa + "</div>";
  }

  function applyQuotaToWatchedRows(courses) {
    const byKey = {};
    courses.forEach((c) => {
      byKey[keyOf(c.kode, c.kelas_nama)] = c;
    });
    watchedList.querySelectorAll(".row").forEach((row) => {
      const k = keyOf(row.dataset.kode, row.dataset.kelas);
      const c = byKey[k];
      if (!c) return;
      const q = row.querySelector(".quota");
      if (q) q.outerHTML = quotaBoxHtml(c.sisa_kuota);
      const title = row.querySelector(".title");
      if (title && c.matakuliah) title.textContent = c.matakuliah;
    });
  }

  function watchedRowHtml(t) {
    return (
      '<div class="row" data-kode="' + t.kode + '" data-kelas="' + t.kelas_nama + '">' +
      quotaBoxHtml(null) +
      '<div class="meta">' +
      '<div class="title">' + (t.matakuliah || "Nama menyusul setelah cek pertama") + "</div>" +
      '<div class="sub">' +
      '<span class="chip">' + t.kode + "</span>" +
      '<span class="chip">Kelas ' + t.kelas_nama + "</span>" +
      (t.dosen ? "<span>" + t.dosen + "</span>" : "") +
      "</div></div>" +
      '<div class="actions"><button class="danger-ghost btn-remove">Hapus</button></div>' +
      "</div>"
    );
  }

  function refreshWatchedEmptyState() {
    const rows = watchedList.querySelectorAll(".row");
    watchedCount.textContent = rows.length;
    const emptyEl = watchedList.querySelector(".empty");
    if (rows.length === 0 && !emptyEl) {
      watchedList.innerHTML =
        '<div class="empty">Belum ada mata kuliah yang dipantau. Tambahkan dari daftar di bawah.</div>';
    } else if (rows.length > 0 && emptyEl) {
      emptyEl.remove();
    }
  }

  async function addTarget(course) {
    const res = await fetch("/api/targets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kode: course.kode,
        kelas_nama: course.kelas_nama,
        matakuliah: course.matakuliah,
        dosen: course.dosen,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert("Gagal menambahkan: " + (err.error || res.status));
      return;
    }
    const t = await res.json();
    const key = keyOf(t.kode, t.kelas_nama);
    if (!watchedKeys.has(key)) {
      watchedKeys.add(key);
      const emptyEl = watchedList.querySelector(".empty");
      if (emptyEl) emptyEl.remove();
      watchedList.insertAdjacentHTML("beforeend", watchedRowHtml(t));
    }
    refreshWatchedEmptyState();
    renderCourseList(courseFilter.value);
  }

  async function removeTarget(kode, kelas) {
    const res = await fetch("/api/targets", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kode, kelas_nama: kelas }),
    });
    if (!res.ok) return;
    watchedKeys.delete(keyOf(kode, kelas));
    refreshWatchedEmptyState();
    renderCourseList(courseFilter.value);
  }

  watchedList.addEventListener("click", (e) => {
    const btn = e.target.closest(".btn-remove");
    if (!btn) return;
    const row = btn.closest(".row");
    if (!row) return;
    if (!confirm("Hapus " + row.dataset.kode + " kelas " + row.dataset.kelas + " dari pantauan?")) return;
    removeTarget(row.dataset.kode, row.dataset.kelas);
    row.remove();
  });

  function courseRowHtml(c) {
    const key = keyOf(c.kode, c.kelas_nama);
    const already = watchedKeys.has(key);
    return (
      '<div class="row" data-kode="' + c.kode + '" data-kelas="' + c.kelas_nama + '">' +
      quotaBoxHtml(c.sisa_kuota) +
      '<div class="meta">' +
      '<div class="title">' + c.matakuliah + "</div>" +
      '<div class="sub">' +
      '<span class="chip">' + c.kode + "</span>" +
      '<span class="chip">Kelas ' + c.kelas_nama + "</span>" +
      '<span class="chip">' + c.sks + " sks</span>" +
      (c.dosen ? "<span>" + c.dosen + "</span>" : "") +
      "</div></div>" +
      '<div class="actions">' +
      (already
        ? '<button disabled>Sudah dipantau</button>'
        : '<button class="primary btn-add">+ Pantau</button>') +
      "</div></div>"
    );
  }

  function renderCourseList(filterText) {
    const q = (filterText || "").trim().toLowerCase();
    const filtered = !q
      ? lastCourses
      : lastCourses.filter(
          (c) =>
            c.kode.toLowerCase().includes(q) ||
            c.matakuliah.toLowerCase().includes(q) ||
            c.kelas_nama.toLowerCase().includes(q)
        );

    if (filtered.length === 0) {
      courseList.innerHTML =
        '<div class="empty">Tidak ada mata kuliah yang cocok.</div>';
      return;
    }

    courseList.innerHTML = filtered.map(courseRowHtml).join("");
  }

  courseList.addEventListener("click", (e) => {
    const btn = e.target.closest(".btn-add");
    if (!btn) return;
    const row = btn.closest(".row");
    const c = lastCourses.find(
      (x) => keyOf(x.kode, x.kelas_nama) === keyOf(row.dataset.kode, row.dataset.kelas)
    );
    if (!c) return;
    btn.disabled = true;
    btn.textContent = "Menambahkan\u2026";
    addTarget(c);
  });

  courseFilter.addEventListener("input", () => renderCourseList(courseFilter.value));

  btnLoadCourses.addEventListener("click", async () => {
    btnLoadCourses.disabled = true;
    const original = btnLoadCourses.textContent;
    btnLoadCourses.textContent = "Mengambil\u2026";
    courseList.innerHTML = '<div class="empty">Menghubungi portal, mohon tunggu\u2026</div>';
    try {
      const res = await fetch("/api/courses");
      const data = await res.json();
      if (!res.ok) {
        courseList.innerHTML =
          '<div class="empty">Gagal ambil daftar: ' + (data.error || res.status) + "</div>";
        return;
      }
      lastCourses = data;
      applyQuotaToWatchedRows(data);
      courseFilter.disabled = false;
      renderCourseList(courseFilter.value);
    } catch (e) {
      courseList.innerHTML = '<div class="empty">Gagal menghubungi server.</div>';
    } finally {
      btnLoadCourses.disabled = false;
      btnLoadCourses.textContent = original;
    }
  });

  refreshStatus();
  setInterval(refreshStatus, 8000);
})();
