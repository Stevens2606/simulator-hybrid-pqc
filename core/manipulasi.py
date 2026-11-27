"""Manipulasi untuk skenario pengujian (manipulasi citra dan manipulasi tanda tangan).

Semua parameter dibuat tetap (tidak acak) supaya pengujian bisa diulang dengan hasil yang sama.
Nilai parameter di bawah ini harus sama dengan yang ditulis di Bab III.

Masukan setiap fungsi: citra bertanda tangan yang dibuka dengan citra.buka_citra() dari file JPEG,
beserta teks paketnya.

Cara hasil manipulasi diserahkan ke verifikasi:
- Manipulasi PIKSEL (satu piksel, bercak, kecerahan/kontras, cropping):
  hasilnya berupa citra di memori dengan paket asli dilampirkan (citra.lampirkan_paket).
  Citra ini sengaja TIDAK disimpan ulang sebagai JPEG, karena kompresi JPEG akan ikut mengubah
  piksel lain, sehingga yang diuji bukan lagi manipulasi yang dimaksud.
- Kompresi ulang JPEG: citra benar-benar dikompres ulang (kualitas JPEG_KUALITAS), lalu paket
  asli disisipkan kembali. Yang diuji: perubahan piksel akibat kompresi.
- Manipulasi TANDA TANGAN: data gambar tidak disentuh; yang diubah hanya segmen paket di
  file JPEG (dihapus, diubah, ditukar, atau diganti). Hasilnya berupa byte file JPEG.
"""

import base64
import io
import json

import numpy as np
from PIL import Image

from . import citra, hybrid

# ---------- Parameter (tetap) ----------
SATU_PIKSEL_DELTA = 10          # perubahan intensitas 1 piksel (dari 256 tingkat)
ROI_POSISI = (0.30, 0.40)       # posisi kiri-atas ROI relatif terhadap lebar, tinggi (area paru)
ROI_UKURAN = (0.10, 0.10)       # ukuran ROI relatif terhadap lebar, tinggi
ROI_DELTA = 60                  # penambahan intensitas untuk "bercak"
KECERAHAN_DELTA = 20            # penambahan intensitas seluruh citra
POTONG_PIKSEL = 10              # baris/kolom tepi yang dibuang di setiap sisi
JPEG_KUALITAS = 90              # kualitas kompresi ulang JPEG


def _ke_array(img):
    return np.array(img, dtype=np.int32)


def _ke_citra(arr, mode):
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode=mode)


# ---------- Manipulasi citra ----------

def ubah_satu_piksel(img, paket):
    arr = _ke_array(img)
    y, x = arr.shape[0] // 2, arr.shape[1] // 2
    delta = SATU_PIKSEL_DELTA if np.max(arr[y, x]) <= 255 - SATU_PIKSEL_DELTA else -SATU_PIKSEL_DELTA
    arr[y, x] = arr[y, x] + delta
    return citra.lampirkan_paket(_ke_citra(arr, img.mode), paket)


def tambah_bercak(img, paket):
    arr = _ke_array(img)
    t, l = arr.shape[0], arr.shape[1]
    y0, x0 = int(t * ROI_POSISI[1]), int(l * ROI_POSISI[0])
    y1, x1 = y0 + max(1, int(t * ROI_UKURAN[1])), x0 + max(1, int(l * ROI_UKURAN[0]))
    arr[y0:y1, x0:x1] = arr[y0:y1, x0:x1] + ROI_DELTA
    return citra.lampirkan_paket(_ke_citra(arr, img.mode), paket)


def ubah_kecerahan_kontras(img, paket):
    arr = _ke_array(img) + KECERAHAN_DELTA
    arr = np.clip(arr, 0, 255)
    lo, hi = arr.min(), arr.max()
    if hi > lo:
        arr = (arr - lo) * 255 // (hi - lo)   # contrast stretching
    return citra.lampirkan_paket(_ke_citra(arr, img.mode), paket)


def potong_tepi(img, paket):
    p = POTONG_PIKSEL
    lebar, tinggi = img.size
    return citra.lampirkan_paket(img.crop((p, p, lebar - p, tinggi - p)), paket)


def kompresi_ulang_jpeg(img, paket):
    """Citra dikompres ulang sebagai JPEG, lalu paket asli disisipkan kembali.

    Paket sengaja dipertahankan agar yang diuji adalah perubahan piksel akibat kompresi,
    bukan hilangnya paket (hilangnya paket sudah diuji di "Penghapusan paket").
    """
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_KUALITAS)
    return citra.sisipkan_paket(buf.getvalue(), paket)


MANIPULASI_CITRA = {
    "Perubahan satu piksel": ubah_satu_piksel,
    "Penambahan objek (bercak) pada area paru": tambah_bercak,
    "Perubahan kecerahan dan kontras": ubah_kecerahan_kontras,
    "Pemotongan (cropping)": potong_tepi,
    "Kompresi ulang JPEG": kompresi_ulang_jpeg,
}


# ---------- Manipulasi tanda tangan ----------

def _ubah_byte(b, posisi=0):
    b = bytearray(b)
    b[posisi % len(b)] ^= 0xFF
    return bytes(b)


def _paket_baru(paket, ubah_ecdsa=False, ubah_pqc=False):
    data = json.loads(paket)
    if ubah_ecdsa:
        sig = base64.b64decode(data["sig_ecdsa"])
        data["sig_ecdsa"] = base64.b64encode(_ubah_byte(sig, len(sig) // 2)).decode()
    if ubah_pqc:
        sig = base64.b64decode(data["sig_pqc"])
        data["sig_pqc"] = base64.b64encode(_ubah_byte(sig, len(sig) // 2)).decode()
    return json.dumps(data, separators=(",", ":"))


def hapus_paket(img, paket, **_):
    return citra.simpan_citra(img, None)


def ubah_isi_paket(img, paket, **_):
    return citra.simpan_citra(img, _paket_baru(paket, ubah_ecdsa=True, ubah_pqc=True))


def tukar_paket(img, paket, paket_citra_lain=None, **_):
    return citra.simpan_citra(img, paket_citra_lain)


def rusak_ecdsa_saja(img, paket, **_):
    return citra.simpan_citra(img, _paket_baru(paket, ubah_ecdsa=True))


def rusak_pqc_saja(img, paket, **_):
    return citra.simpan_citra(img, _paket_baru(paket, ubah_pqc=True))


def tandatangani_ulang_kunci_penyerang(img, paket, **_):
    kombinasi = json.loads(paket)["kombinasi"]
    kunci_penyerang = hybrid.bangkitkan_kunci(kombinasi)
    nilai_hash = citra.hitung_hash(img)
    sig_e, sig_p = hybrid.tandatangani(nilai_hash, kunci_penyerang)
    return citra.simpan_citra(img, citra.buat_paket(kombinasi, sig_e, sig_p))


MANIPULASI_TANDA_TANGAN = {
    "Penghapusan paket": hapus_paket,
    "Perubahan isi paket": ubah_isi_paket,
    "Penukaran paket dari citra lain": tukar_paket,
    "Pemalsuan sebagian (ECDSA dirusak)": rusak_ecdsa_saja,
    "Pemalsuan sebagian (pasca-kuantum dirusak)": rusak_pqc_saja,
    "Penandatanganan ulang dengan kunci penyerang": tandatangani_ulang_kunci_penyerang,
}