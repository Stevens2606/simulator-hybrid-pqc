"""Simulator berbasis web: Hybrid Post-Quantum Digital Signature untuk integritas citra medis.

Rancangan mengikuti Bab III (subbab 3.6):
  /                -> diarahkan ke /sign (tanpa dashboard)
  /sign            -> Sign Image                 (UC-01)
  /unduh/<id>      -> unduh citra JPEG bertanda tangan
  /gambar/<id>     -> pratinjau citra bertanda tangan / citra uji
  /asli/<id>       -> pratinjau citra asli sebelum ditandatangani (sisi pengirim)
  /verifikasi      -> Status and Verification    (UC-02), alur pengirim -> penerima
  /eksternal       -> External File Verification (UC-03)
  /kinerja         -> Performance Comparison     (UC-04)
  /reset           -> menghapus data sesi

Citra tetap berformat JPEG: paket tanda tangan disisipkan ke metadata JPEG (segmen APP15)
tanpa mengompres ulang gambar, sehingga nilai piksel tidak berubah (lihat core/citra.py).

Antarmuka menggunakan Bahasa Inggris (KNF-02). Status dan alasan dari core (Bahasa
Indonesia) diterjemahkan di file ini sebelum ditampilkan. Script pengujian tetap memakai
status "VALID" / "TIDAK VALID".

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
app.jinja_env.globals["zip"] = zip                    # dipakai template untuk menandai karakter hash yang berbeda

_SESI = {}                     # {kode_sesi: data sesi}, hanya di memori server
MAKS_CITRA_PER_SESI = 20       # agar memori server tidak penuh

# Urutan dan warna keluarga algoritma (untuk pilihan kombinasi, tabel, dan grafik)
URUTAN_ALGORITMA = ["ML-DSA", "Falcon", "SLH-DSA-SHA2-f", "SLH-DSA-SHA2-s", "SLH-DSA-SHAKE-f", "SLH-DSA-SHAKE-s"]
WARNA_ALGORITMA = {"ML-DSA": "#5B7DB1", "Falcon": "#E39B3A", "SLH-DSA-SHA2-f": "#5BA36B",
                   "SLH-DSA-SHA2-s": "#2E6B30", "SLH-DSA-SHAKE-f": "#B565A7", "SLH-DSA-SHAKE-s": "#7A3E73"}

# ---------------------------------------------------------------- terjemahan tampilan (KNF-02)
STATUS_EN = {"VALID": "VALID", "TIDAK VALID": "INVALID"}

# Alasan mengikuti Tabel 3.13 (Aturan Penentuan Hasil Verifikasi).
# Kunci di kiri HARUS sama persis dengan teks alasan di core/proses.py.
# Kondisi 1 (paket tidak ditemukan / tidak lengkap / kunci publik tidak tersedia) memakai alasan
# "Signature cannot be checked", diikuti penyebabnya agar pengguna tahu masalahnya.
ALASAN_EN = {
    "Tanda tangan tidak ditemukan pada citra.":
        "Signature cannot be checked: signature not found in the image.",
    "Paket tanda tangan rusak atau tidak lengkap.":
        "Signature cannot be checked: signature package is incomplete.",
    "Kunci publik untuk kombinasi ini tidak tersedia.":
        "Signature cannot be checked: public key is not available in this session.",
    "Citra asli dan tidak berubah sejak ditandatangani.": "Image has not changed since it was signed.",
    "Kedua tanda tangan tidak cocok: citra telah berubah atau tanda tangan tidak sah.":
        "Both signatures do not match.",
    "Tanda tangan ECDSA tidak cocok.": "ECDSA signature does not match.",
    "Tanda tangan pasca-kuantum tidak cocok.": "Post-quantum signature does not match.",
}

MANIPULASI_EN = {
    "Perubahan satu piksel": "Single pixel change",
    "Penambahan objek (bercak) pada area paru": "Added spot (object) in the lung area",
    "Perubahan kecerahan dan kontras": "Brightness and contrast change",
    "Pemotongan (cropping)": "Cropping",
    "Kompresi ulang JPEG": "JPEG recompression",
    "Penghapusan paket": "Package removal",
    "Perubahan isi paket": "Package content change",
    "Penukaran paket dari citra lain": "Package swap from another image",
    "Pemalsuan sebagian (ECDSA dirusak)": "Partial forgery (ECDSA damaged)",
    "Pemalsuan sebagian (pasca-kuantum dirusak)": "Partial forgery (post-quantum damaged)",
    "Penandatanganan ulang dengan kunci penyerang": "Re-signing with the attacker's key",
}


def en_status(status):
    return STATUS_EN.get(status, status)


def en_alasan(alasan):
    return ALASAN_EN.get(alasan, alasan)


app.jinja_env.globals["en_manipulasi"] = lambda nama: MANIPULASI_EN.get(nama, nama)


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
    """Kunci dibangkitkan satu kali per kombinasi per sesi."""
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
    status = status_dari(hasil)
    return {
        "status": status,                       # status asli dari core (VALID / TIDAK VALID)
        "status_en": en_status(status),         # status yang ditampilkan (VALID / INVALID)
        "ecdsa": cocok(hasil, "ecdsa"),
        "pqc": cocok(hasil, "pqc"),
        "alasan": en_alasan(hasil.get("alasan", "")),
        "kombinasi": hasil.get("kombinasi"),
        "waktu_ms": hasil.get("waktu_verifikasi_ms", 0.0),
    }


def gambar_pratinjau(data, sisi=520):
    """Gambar kecil untuk ditampilkan di browser saja (bukan file hasil).

    data bisa berupa byte file JPEG atau objek citra (hasil manipulasi piksel di memori).
    Pratinjau hanya diperkecil untuk tampilan; file hasil penandatanganan tidak ikut diubah.
    """
    img = data.copy() if isinstance(data, Image.Image) else Image.open(io.BytesIO(data))
    img.thumbnail((sisi, sisi))
    buf = io.BytesIO()
    img.convert("L" if img.mode not in ("L", "RGB") else img.mode).save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def kombinasi_per_algoritma():
    """Mengelompokkan 17 kombinasi per keluarga algoritma, untuk pilihan di halaman Sign Image."""
    kelompok = {a: [] for a in URUTAN_ALGORITMA}
    for kode, data in KOMBINASI.items():
        kelompok.setdefault(data["algoritma"], []).append((kode, data))
    return [(a, daftar) for a, daftar in kelompok.items() if daftar]


@app.context_processor
def data_umum():
    return {"KOMBINASI": KOMBINASI, "halaman": request.endpoint}


@app.errorhandler(413)
def terlalu_besar(_):
    return render_template("pesan.html", pesan="The file exceeds the 30 MB upload limit."), 413


@app.route("/")
def beranda():
    """Halaman awal langsung diarahkan ke Sign Image (simulator tanpa dashboard)."""
    return redirect(url_for("sign"))


# ---------------------------------------------------------------- UC-01 Sign Image
@app.route("/sign", methods=["GET", "POST"])
def sign():
    s = sesi()
    pesan, hasil = None, None
    if request.method == "POST":
        berkas = request.files.get("citra")
        kombinasi = request.form.get("kombinasi")
        if not berkas or not berkas.filename:
            pesan = "Please choose an image file first."
        elif Path(berkas.filename).suffix.lower() not in (".jpg", ".jpeg"):
            pesan = "Unsupported image format. Please upload a JPEG file."
        elif kombinasi not in KOMBINASI:
            pesan = "Please choose one of the hybrid combinations."
        else:
            data_asli = berkas.read()                 # file asli sebelum ditandatangani
            try:
                img = citra.buka_citra(data_asli)
            except Exception:
                img = None
                pesan = "The file cannot be read as an image."
            if img is not None:
                kunci = kunci_untuk(s, kombinasi)
                jpeg_ttd, info = proses.tandatangani_citra(img, kunci)
                cek = proses.verifikasi_citra(citra.buka_citra(jpeg_ttd), kunci_publik_sesi(s))
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
                    "file_asli": info.get("ukuran_file_asli"),
                    "file_bertanda": info.get("ukuran_file_bertanda"),
                    "pertambahan": info.get("pertambahan_file"),
                    "kunci": ukuran_kunci(kunci),
                    "waktu": time.strftime("%H:%M:%S"),
                }
                s["citra"].append({"id": hasil["id"], "asli": data_asli, "file": jpeg_ttd, "info": hasil})
                s["citra"] = s["citra"][-MAKS_CITRA_PER_SESI:]
                s["riwayat"].append(hasil)
    return render_template("sign.html", pesan=pesan, hasil=hasil, kelompok=kombinasi_per_algoritma(),
                           dipilih=request.form.get("kombinasi"))


def _cari_citra(s, id_citra):
    for c in s["citra"]:
        if c["id"] == id_citra:
            return c
    abort(404)


@app.route("/unduh/<id_citra>")
def unduh(id_citra):
    c = _cari_citra(sesi(), id_citra)
    return send_file(io.BytesIO(c["file"]), mimetype="image/jpeg", as_attachment=True,
                     download_name=f"{c['info']['nama']}_signed.jpg")


@app.route("/gambar/<id_citra>")
def gambar(id_citra):
    s = sesi()
    if id_citra == "uji":
        if not s["uji"]:
            abort(404)
        data = s["uji"]
    else:
        data = _cari_citra(s, id_citra)["file"]
    try:
        return send_file(io.BytesIO(gambar_pratinjau(data)), mimetype="image/jpeg")
    except Exception:
        abort(404)


@app.route("/asli/<id_citra>")
def gambar_asli(id_citra):
    """Pratinjau citra asli sebelum ditandatangani (sisi pengirim)."""
    c = _cari_citra(sesi(), id_citra)
    try:
        return send_file(io.BytesIO(gambar_pratinjau(c["asli"])), mimetype="image/jpeg")
    except Exception:
        abort(404)


# ---------------------------------------------------------------- UC-02 Status and Verification
# Halaman ini memperagakan alur pengiriman citra:
#   sisi pengirim : citra asli -> hash asli -> ditandatangani (sigma1 ECDSA, sigma2 PQC)
#   perjalanan    : citra dapat mengalami manipulasi (atau tidak)
#   sisi penerima : hash dihitung ulang -> sigma1 dan sigma2 diperiksa dengan kunci publik -> aturan AND
@app.route("/verifikasi", methods=["GET", "POST"])
def verifikasi():
    s = sesi()
    hasil, dipilih, jenis = None, None, "tanpa"
    if request.method == "POST" and s["citra"]:
        dipilih = _cari_citra(s, request.form.get("citra"))
        jenis = request.form.get("manipulasi", "tanpa")
        img_ttd = citra.buka_citra(dipilih["file"])
        paket = citra.baca_paket(img_ttd)
        if jenis == "tanpa":
            label, data_uji = "None", dipilih["file"]
        elif jenis in manipulasi.MANIPULASI_CITRA:
            label, data_uji = MANIPULASI_EN.get(jenis, jenis), manipulasi.MANIPULASI_CITRA[jenis](img_ttd, paket)
        elif jenis in manipulasi.MANIPULASI_TANDA_TANGAN:
            lain = [c for c in s["citra"] if c["id"] != dipilih["id"]
                    and c["info"]["kombinasi"] == dipilih["info"]["kombinasi"]]
            paket_lain = citra.baca_paket(citra.buka_citra(lain[-1]["file"])) if lain else None
            if jenis.startswith("Penukaran") and paket_lain is None:
                return render_template("verifikasi.html", hasil=None, dipilih=dipilih,
                                       pesan="Package swap needs at least two images signed "
                                             "with the same combination.",
                                       m_citra=manipulasi.MANIPULASI_CITRA,
                                       m_ttd=manipulasi.MANIPULASI_TANDA_TANGAN, daftar=s["citra"], jenis=jenis)
            label = MANIPULASI_EN.get(jenis, jenis)
            data_uji = manipulasi.MANIPULASI_TANDA_TANGAN[jenis](img_ttd, paket, paket_citra_lain=paket_lain)
        else:
            abort(400)
        img_uji = citra.buka_citra(data_uji)
        hasil = ringkas_verifikasi(proses.verifikasi_citra(img_uji, kunci_publik_sesi(s)))
        # sisi pengirim: hash citra asli (dihitung saat penandatanganan)
        hasil["hash_ttd"] = dipilih["info"]["hash"]
        # sisi penerima: hash dihitung ulang dari citra yang diterima
        hasil["hash_uji"] = citra.hitung_hash(img_uji).hex()
        hasil["ada_paket"] = citra.baca_paket(img_uji) is not None
        hasil["manipulasi"] = label
        hasil["harapan"] = "VALID" if jenis == "tanpa" else "INVALID"
        s["uji"] = data_uji          # byte JPEG, atau citra di memori untuk manipulasi piksel
        s["riwayat"].append({"kombinasi": dipilih["info"]["kombinasi"], "verif_ms": hasil["waktu_ms"],
                             "hanya_verifikasi": True})
    return render_template("verifikasi.html", hasil=hasil, dipilih=dipilih, pesan=None,
                           m_citra=manipulasi.MANIPULASI_CITRA, m_ttd=manipulasi.MANIPULASI_TANDA_TANGAN,
                           daftar=s["citra"], waktu=time.time(), jenis=jenis)


# ---------------------------------------------------------------- UC-03 External File Verification
@app.route("/eksternal", methods=["GET", "POST"])
def eksternal():
    s = sesi()
    hasil, pesan, paket_info = None, None, None
    if request.method == "POST":
        berkas = request.files.get("citra")
        if not berkas or not berkas.filename:
            pesan = "Please choose an image file first."
        elif Path(berkas.filename).suffix.lower() not in (".jpg", ".jpeg"):
            pesan = "Unsupported file format. Please upload a JPEG file."     # UC-03 alur lain
        else:
            data = berkas.read()
            try:
                img = citra.buka_citra(data)
            except Exception:
                img, pesan = None, "The file cannot be read as an image."
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
                hasil["hash_uji"] = citra.hitung_hash(img).hex()
                s["uji"] = data
    return render_template("eksternal.html", hasil=hasil, pesan=pesan, paket=paket_info,
                           ada_kunci=bool(s["kunci"]), waktu=time.time())


# ---------------------------------------------------------------- UC-04 Performance Comparison
@app.route("/kinerja")
def kinerja():
    s = sesi()
    baris = []
    for k, data in KOMBINASI.items():
        ttd = [r for r in s["riwayat"] if r["kombinasi"] == k and not r.get("hanya_verifikasi")]
        ver = [r["verif_ms"] for r in s["riwayat"] if r["kombinasi"] == k]
        if not ttd:
            continue
        rata = lambda kunci: statistics.mean(r[kunci] for r in ttd)
        baris.append({
            "kombinasi": k, "algoritma": data["algoritma"], "level": data["level_nist"],
            "warna": WARNA_ALGORITMA.get(data["algoritma"], "#5B7DB1"),
            "n_ttd": len(ttd), "n_ver": len(ver),
            "keygen": s["keygen_ms"].get(k, 0.0),
            "ttd": rata("ttd_ms"), "total": rata("total_ms"),
            "verif": statistics.mean(ver) if ver else 0.0,
            "kunci": ttd[-1]["kunci"], "sig_ecdsa": ttd[-1]["sig_ecdsa"], "sig_pqc": ttd[-1]["sig_pqc"],
            "pertambahan": rata("pertambahan"),
        })
    # urutkan: keluarga algoritma, lalu level NIST
    baris.sort(key=lambda b: (URUTAN_ALGORITMA.index(b["algoritma"]) if b["algoritma"] in URUTAN_ALGORITMA else 99,
                              b["level"]))
    maks_ttd = max([b["ttd"] for b in baris] + [1e-9])
    maks_ver = max([b["verif"] for b in baris] + [1e-9])
    legenda = [(a, WARNA_ALGORITMA[a]) for a in URUTAN_ALGORITMA if any(b["algoritma"] == a for b in baris)]
    return render_template("kinerja.html", baris=baris, maks_ttd=maks_ttd, maks_ver=maks_ver, legenda=legenda)


@app.route("/reset")
def reset():
    _SESI.pop(session.get("kode"), None)
    session.clear()
    return redirect(url_for("beranda"))


if __name__ == "__main__":
    app.run(debug=True)