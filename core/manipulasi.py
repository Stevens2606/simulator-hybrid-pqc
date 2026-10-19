
"""Manipulasi untuk skenario pengujian (Tabel 2 dan Tabel 3 di proposal).

Semua parameter dibuat tetap (tidak acak) supaya pengujian bisa diulang dengan hasil yang sama.
Nilai parameter di bawah ini masih usulan awal; sesuaikan dengan keputusan tim, lalu
tuliskan nilainya di Bab III.
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


def _simpan_dengan_paket(img_baru, paket):
    """Simpan ulang sebagai PNG dengan paket tanda tangan yang SAMA (agar yang diuji = perubahan piksel)."""
    return citra.simpan_png(img_baru, paket)


# ---------- Tabel 2: manipulasi citra ----------

def ubah_satu_piksel(img, paket):
    arr = _ke_array(img)
    y, x = arr.shape[0] // 2, arr.shape[1] // 2
    delta = SATU_PIKSEL_DELTA if np.max(arr[y, x]) <= 255 - SATU_PIKSEL_DELTA else -SATU_PIKSEL_DELTA
    arr[y, x] = arr[y, x] + delta
    return _simpan_dengan_paket(_ke_citra(arr, img.mode), paket)


def tambah_bercak(img, paket):
    arr = _ke_array(img)
    t, l = arr.shape[0], arr.shape[1]
    y0, x0 = int(t * ROI_POSISI[1]), int(l * ROI_POSISI[0])
    y1, x1 = y0 + max(1, int(t * ROI_UKURAN[1])), x0 + max(1, int(l * ROI_UKURAN[0]))
    arr[y0:y1, x0:x1] = arr[y0:y1, x0:x1] + ROI_DELTA
    return _simpan_dengan_paket(_ke_citra(arr, img.mode), paket)


def ubah_kecerahan_kontras(img, paket):
    arr = _ke_array(img) + KECERAHAN_DELTA
    arr = np.clip(arr, 0, 255)
    lo, hi = arr.min(), arr.max()
    if hi > lo:
        arr = (arr - lo) * 255 // (hi - lo)   # contrast stretching
    return _simpan_dengan_paket(_ke_citra(arr, img.mode), paket)


def potong_tepi(img, paket):
    p = POTONG_PIKSEL
    lebar, tinggi = img.size
    return _simpan_dengan_paket(img.crop((p, p, lebar - p, tinggi - p)), paket)


def kompresi_ulang_jpeg(img, paket):
    """Disimpan sebagai JPEG: nilai piksel berubah dan metadata PNG ikut hilang."""
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_KUALITAS)
    return buf.getvalue()


MANIPULASI_CITRA = {
    "Perubahan satu piksel": ubah_satu_piksel,
    "Penambahan objek (bercak) pada area paru": tambah_bercak,
    "Perubahan kecerahan dan kontras": ubah_kecerahan_kontras,
    "Pemotongan (cropping)": potong_tepi,
    "Kompresi ulang JPEG": kompresi_ulang_jpeg,
}


# ---------- Tabel 3: manipulasi tanda tangan ----------

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
    return citra.simpan_png(img)


def ubah_isi_paket(img, paket, **_):
    return citra.simpan_png(img, _paket_baru(paket, ubah_ecdsa=True, ubah_pqc=True))


def tukar_paket(img, paket, paket_citra_lain=None, **_):
    return citra.simpan_png(img, paket_citra_lain)


def rusak_ecdsa_saja(img, paket, **_):
    return citra.simpan_png(img, _paket_baru(paket, ubah_ecdsa=True))


def rusak_pqc_saja(img, paket, **_):
    return citra.simpan_png(img, _paket_baru(paket, ubah_pqc=True))


def tandatangani_ulang_kunci_penyerang(img, paket, **_):
    kombinasi = json.loads(paket)["kombinasi"]
    kunci_penyerang = hybrid.bangkitkan_kunci(kombinasi)
    nilai_hash = citra.hitung_hash(img)
    sig_e, sig_p = hybrid.tandatangani(kunci_penyerang, nilai_hash)
    return citra.simpan_png(img, citra.buat_paket(kombinasi, sig_e, sig_p))


MANIPULASI_TANDA_TANGAN = {
    "Penghapusan paket": hapus_paket,
    "Perubahan isi paket": ubah_isi_paket,
    "Penukaran paket dari citra lain": tukar_paket,
    "Pemalsuan sebagian (ECDSA dirusak)": rusak_ecdsa_saja,
    "Pemalsuan sebagian (pasca-kuantum dirusak)": rusak_pqc_saja,
    "Penandatanganan ulang dengan kunci penyerang": tandatangani_ulang_kunci_penyerang,
}
