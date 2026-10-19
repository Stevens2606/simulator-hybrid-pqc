"""Simulator berbasis web: Hybrid Post-Quantum Digital Signature untuk integritas citra medis.

Rancangan mengikuti Bab III (subbab 3.7):
  /                -> diarahkan ke halaman Sign Citra
  /sign            -> Sign Citra                 (UC-01)
  /unduh/<id>      -> unduh citra PNG bertanda tangan
  /gambar/<id>     -> pratinjau citra (untuk ditampilkan di halaman)
  /verifikasi      -> Status dan Verifikasi      (UC-02)
  /eksternal       -> Verifikasi File Eksternal  (UC-03)
  /kinerja         -> Perbandingan Kinerja       (UC-04)
  /reset           -> menghapus data sesi

Data sesi (kunci, citra bertanda tangan, hasil pengukuran) disimpan di memori server.
Cookie pada browser hanya berisi kode pengenal sesi, sehingga kunci privat tidak pernah
dikirim ke browser.

Cara menjalankan (di WSL, venv-wsl aktif, dari folder simulator_hybrid):
    python app.py
lalu buka http://127.0.0.1:5000 di browser.
"""

import io
import secrets
import statistics
import time
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from flask import Flask, abort, redirect, render_template, request, send_file, session, url_for
from PIL import Image

from core import citra, hybrid, manipulasi, proses
from core.kombinasi import KOMBINASI

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024   # batas unggah 30 MB

_SESI = {}                     # {kode_sesi: data sesi}, hanya di memori server
MAKS_CITRA_PER_SESI = 20       # agar memori server tidak penuh


# ---------------------------------------------------------------- bantuan
def sesi():
    """Mengambil data sesi milik browser ini (membuat baru jika belum ada)."""
    kode = session.get("kode")
    if kode not in _SESI:
        kode = secrets.token_hex(8)
        session["kode"] = kode
        _SESI[kode] = {"kunci": {}, "keygen_ms": {}, "citra": [], "riwayat": [], "uji": None}
    return _SESI[kode]


def kunci_untuk(s, kombinasi):
    """Kunci dibangkitkan satu kali per kombinasi per sesi (Gambar 3.9 langkah 3)."""
    if kombinasi not in s["kunci"]:
        kunci, ms = proses.ukur_keygen(kombinasi)
        s["kunci"][kombinasi] = kunci
        s["keygen_ms"][kombinasi] = ms
    return s["kunci"][kombinasi]


def kunci_publik_sesi(s):
    return {k: hybrid.kunci_publik_dari(v) for k, v in s["kunci"].items()}


def status_dari(hasil):
    if "status" in hasil:
        return hasil["status"]
    return "VALID" if hasil.get("valid") else "TIDAK VALID"


def cocok(hasil, nama):
    """Hasil pemeriksaan satu tanda tangan: True / False / None (tidak diperiksa)."""
    return hasil.get(f"{nama}_cocok", hasil.get(nama))


def _ukuran(obj):
    if isinstance(obj, (bytes, bytearray)):
        return len(obj)
    if hasattr(obj, "private_numbers"):
        return (obj.curve.key_size + 7) // 8
    if hasattr(obj, "public_bytes"):
        return len(obj.public_bytes(serialization.Encoding.X962,
                                    serialization.PublicFormat.UncompressedPoint))
    return None


def ukuran_kunci(kunci):
    ambil = kunci.get if isinstance(kunci, dict) else (lambda n: getattr(kunci, n, None))
    return {
        "ecdsa_publik": _ukuran(ambil("ecdsa_publik") or ambil("ecdsa_publik_bytes")),
        "ecdsa_privat": _ukuran(ambil("ecdsa_privat")),
        "pqc_publik": _ukuran(ambil("pqc_publik")),
        "pqc_privat": _ukuran(ambil("pqc_privat")),
    }


def ringkas_verifikasi(hasil):
    return {
        "status": status_dari(hasil),
        "ecdsa": cocok(hasil, "ecdsa"),
        "pqc": cocok(hasil, "pqc"),
        "alasan": hasil.get("alasan", ""),
        "kombinasi": hasil.get("kombinasi"),
        "waktu_ms": hasil.get("waktu_verifikasi_ms", 0.0),
    }


def png_pratinjau(data, sisi=520):
    img = Image.open(io.BytesIO(data))
    img.thumbnail((sisi, sisi))
    buf = io.BytesIO()
    img.convert("L" if img.mode not in ("L", "RGB") else img.mode).save(buf, format="PNG")
    return buf.getvalue()


@app.context_processor
def data_umum():
    return {"KOMBINASI": KOMBINASI, "halaman": request.endpoint}


@app.errorhandler(413)
def terlalu_besar(_):
    return render_template("pesan.html", pesan="Ukuran file melebihi batas 30 MB."), 413


# ---------------------------------------------------------------- UC-01 Sign Citra
@app.route("/")
def beranda():
    return redirect(url_for("sign"))


@app.route("/sign", methods=["GET", "POST"])
def sign():
    s = sesi()
    pesan, hasil = None, None
    if request.method == "POST":
        berkas = request.files.get("citra")
        kombinasi = request.form.get("kombinasi")
        if not berkas or not berkas.filename:
            pesan = "Pilih file citra terlebih dahulu."
        elif Path(berkas.filename).suffix.lower() not in (".jpg", ".jpeg", ".png"):
            pesan = "Format citra tidak didukung. Gunakan file JPEG atau PNG."
        elif kombinasi not in KOMBINASI:
            pesan = "Pilih salah satu kombinasi hybrid."
        else:
            try:
                img = citra.buka_citra(berkas.read())
            except Exception:
                img = None
                pesan = "File tidak dapat dibaca sebagai citra."
            if img is not None:
                kunci = kunci_untuk(s, kombinasi)
                png, info = proses.tandatangani_citra(img, kunci)
                cek = proses.verifikasi_citra(citra.buka_citra(png), kunci_publik_sesi(s))
                hasil = {
                    "id": secrets.token_hex(4),
                    "nama": Path(berkas.filename).stem,
                    "kombinasi": kombinasi,
                    "lebar": img.size[0], "tinggi": img.size[1], "mode": img.mode,
                    "hash": citra.hitung_hash(img).hex(),
                    "keygen_ms": s["keygen_ms"][kombinasi],
                    "hash_ms": info.get("waktu_hash_ms", 0.0),
                    "ttd_ms": info.get("waktu_tanda_tangan_ms", 0.0),
                    "simpan_ms": info.get("waktu_simpan_ms", 0.0),
                    "total_ms": info.get("waktu_total_ms", 0.0),
                    "verif_ms": cek.get("waktu_verifikasi_ms", 0.0),
                    "sig_ecdsa": info.get("ukuran_sig_ecdsa"),
                    "sig_pqc": info.get("ukuran_sig_pqc"),
                    "paket": info.get("ukuran_paket"),
                    "png_polos": info.get("ukuran_png_polos"),
                    "png_bertanda": info.get("ukuran_png_bertanda"),
                    "pertambahan": info.get("pertambahan_file"),
                    "kunci": ukuran_kunci(kunci),
                    "waktu": time.strftime("%H:%M:%S"),
                }
                s["citra"].append({"id": hasil["id"], "png": png, "info": hasil})
                s["citra"] = s["citra"][-MAKS_CITRA_PER_SESI:]
                s["riwayat"].append(hasil)
    return render_template("sign.html", pesan=pesan, hasil=hasil)


def _cari_citra(s, id_citra):
    for c in s["citra"]:
        if c["id"] == id_citra:
            return c
    abort(404)


@app.route("/unduh/<id_citra>")
def unduh(id_citra):
    c = _cari_citra(sesi(), id_citra)
    return send_file(io.BytesIO(c["png"]), mimetype="image/png", as_attachment=True,
                     download_name=f"{c['info']['nama']}_bertanda.png")


@app.route("/gambar/<id_citra>")
def gambar(id_citra):
    s = sesi()
    if id_citra == "uji":
        if not s["uji"]:
            abort(404)
        data = s["uji"]
    else:
        data = _cari_citra(s, id_citra)["png"]
    try:
        return send_file(io.BytesIO(png_pratinjau(data)), mimetype="image/png")
    except Exception:
        abort(404)


# ---------------------------------------------------------------- UC-02 Status dan Verifikasi
@app.route("/verifikasi", methods=["GET", "POST"])
def verifikasi():
    s = sesi()
    hasil, dipilih, jenis = None, None, "tanpa"
    if request.method == "POST" and s["citra"]:
        dipilih = _cari_citra(s, request.form.get("citra"))
        jenis = request.form.get("manipulasi", "tanpa")
        img_ttd = citra.buka_citra(dipilih["png"])
        paket = citra.baca_paket(img_ttd)
        if jenis == "tanpa":
            label, data_uji = "Tanpa manipulasi", dipilih["png"]
        elif jenis in manipulasi.MANIPULASI_CITRA:
            label, data_uji = jenis, manipulasi.MANIPULASI_CITRA[jenis](img_ttd, paket)
        elif jenis in manipulasi.MANIPULASI_TANDA_TANGAN:
            lain = [c for c in s["citra"] if c["id"] != dipilih["id"]
                    and c["info"]["kombinasi"] == dipilih["info"]["kombinasi"]]
            paket_lain = citra.baca_paket(citra.buka_citra(lain[-1]["png"])) if lain else None
            if jenis.startswith("Penukaran") and paket_lain is None:
                return render_template("verifikasi.html", hasil=None, dipilih=dipilih,
                                       pesan="Penukaran paket membutuhkan minimal dua citra yang "
                                             "ditandatangani dengan kombinasi yang sama.",
                                       m_citra=manipulasi.MANIPULASI_CITRA,
                                       m_ttd=manipulasi.MANIPULASI_TANDA_TANGAN, daftar=s["citra"], jenis=jenis)
            label = jenis
            data_uji = manipulasi.MANIPULASI_TANDA_TANGAN[jenis](img_ttd, paket, paket_citra_lain=paket_lain)
        else:
            abort(400)
        hasil = ringkas_verifikasi(proses.verifikasi_citra(citra.buka_citra(data_uji), kunci_publik_sesi(s)))
        hasil["manipulasi"] = label
        hasil["harapan"] = "VALID" if jenis == "tanpa" else "TIDAK VALID"
        s["uji"] = data_uji
        s["riwayat"].append({"kombinasi": dipilih["info"]["kombinasi"], "verif_ms": hasil["waktu_ms"],
                             "hanya_verifikasi": True})
    return render_template("verifikasi.html", hasil=hasil, dipilih=dipilih, pesan=None,
                           m_citra=manipulasi.MANIPULASI_CITRA, m_ttd=manipulasi.MANIPULASI_TANDA_TANGAN,
                           daftar=s["citra"], waktu=time.time(), jenis=jenis)


# ---------------------------------------------------------------- UC-03 Verifikasi File Eksternal
@app.route("/eksternal", methods=["GET", "POST"])
def eksternal():
    s = sesi()
    hasil, pesan, paket_info = None, None, None
    if request.method == "POST":
        berkas = request.files.get("citra")
        if not berkas or not berkas.filename:
            pesan = "Pilih file citra terlebih dahulu."
        else:
            data = berkas.read()
            try:
                img = citra.buka_citra(data)
            except Exception:
                img, pesan = None, "File tidak dapat dibaca sebagai citra."
            if img is not None:
                paket = citra.baca_paket(img)
                if paket:
                    try:
                        komb, sig_e, sig_p = citra.urai_paket(paket)
                        paket_info = {"kombinasi": komb, "sig_ecdsa": len(sig_e), "sig_pqc": len(sig_p)}
                    except Exception:
                        paket_info = None
                hasil = ringkas_verifikasi(proses.verifikasi_citra(img, kunci_publik_sesi(s)))
                hasil["nama"] = berkas.filename
                s["uji"] = data
    return render_template("eksternal.html", hasil=hasil, pesan=pesan, paket=paket_info,
                           ada_kunci=bool(s["kunci"]), waktu=time.time())


# ---------------------------------------------------------------- UC-04 Perbandingan Kinerja
@app.route("/kinerja")
def kinerja():
    s = sesi()
    baris = []
    for k in KOMBINASI:
        ttd = [r for r in s["riwayat"] if r["kombinasi"] == k and not r.get("hanya_verifikasi")]
        ver = [r["verif_ms"] for r in s["riwayat"] if r["kombinasi"] == k]
        if not ttd:
            continue
        rata = lambda kunci: statistics.mean(r[kunci] for r in ttd)
        baris.append({
            "kombinasi": k, "n_ttd": len(ttd), "n_ver": len(ver),
            "keygen": s["keygen_ms"].get(k, 0.0),
            "ttd": rata("ttd_ms"), "total": rata("total_ms"),
            "verif": statistics.mean(ver) if ver else 0.0,
            "kunci": ttd[-1]["kunci"], "sig_pqc": ttd[-1]["sig_pqc"],
            "pertambahan": rata("pertambahan"),
        })
    maks_ttd = max([b["ttd"] for b in baris] + [1e-9])
    maks_ver = max([b["verif"] for b in baris] + [1e-9])
    return render_template("kinerja.html", baris=baris, maks_ttd=maks_ttd, maks_ver=maks_ver)


@app.route("/reset")
def reset():
    _SESI.pop(session.get("kode"), None)
    session.clear()
    return redirect(url_for("sign"))


if __name__ == "__main__":
    app.run(debug=True)
