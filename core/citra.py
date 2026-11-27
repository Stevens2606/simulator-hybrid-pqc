# Pengolahan citra: membaca piksel, menghitung hash, serta menyisipkan dan
# membaca paket tanda tangan di metadata file JPEG.
#
# Citra TETAP berformat JPEG. Paket tanda tangan (teks JSON) disisipkan ke byte
# file JPEG asli sebagai segmen aplikasi APP15, tanpa mendekode dan tanpa
# mengompres ulang data gambarnya. Karena data gambar tidak disentuh, nilai
# piksel tetap sama persis dan hash saat verifikasi sama dengan saat penandatanganan.
#
# Susunan file JPEG bertanda tangan:
#   FFD8 (awal) | segmen APPn bawaan (JFIF/EXIF, bila ada) | segmen APP15 "HybridSignature" (1 atau lebih)
#   | tabel, info ukuran, data gambar (tidak berubah) | FFD9 (akhir)
#
# Satu segmen JPEG paling besar 65.535 byte (termasuk 2 byte panjang). Paket yang lebih
# besar (mis. SLH-DSA-256f) dipecah ke beberapa segmen, masing-masing diberi nomor bagian.

import base64
import hashlib
import io
import json
import struct
from pathlib import Path

from PIL import Image

KUNCI_METADATA = "HybridSignature"
VERSI_PAKET = 1

PENANDA_SEGMEN = 0xEF                                  # APP15 (marker FFEF)
ID_SEGMEN = KUNCI_METADATA.encode("ascii") + b"\x00"   # 16 byte di awal isi segmen
MAKS_ISI_SEGMEN = 65535 - 2                            # panjang isi segmen maksimum
MAKS_POTONGAN = MAKS_ISI_SEGMEN - len(ID_SEGMEN) - 2   # dikurangi ID dan 2 byte nomor bagian


# ---------------------------------------------------------------- membuka citra & hash
def buka_citra(sumber):
    """Membuka citra dari path file, bytes, atau objek Image, lalu memuat nilai pikselnya.

    Byte file aslinya disimpan di atribut `berkas_jpeg`, supaya paket bisa dibaca dan
    disisipkan langsung ke byte file tanpa mengompres ulang gambar.
    """
    if isinstance(sumber, Image.Image):          # sudah berupa citra (mis. hasil manipulasi piksel)
        return sumber
    if isinstance(sumber, (bytes, bytearray)):
        data = bytes(sumber)
    else:
        data = Path(sumber).read_bytes()
    img = Image.open(io.BytesIO(data))
    img.load()
    img.berkas_jpeg = data
    return img


def hitung_hash(img):
    """SHA-256 dari lebar, tinggi, dan nilai piksel citra (hasilnya 32 byte)."""
    lebar, tinggi = img.size
    h = hashlib.sha256()
    h.update(lebar.to_bytes(4, "big"))
    h.update(tinggi.to_bytes(4, "big"))
    h.update(img.tobytes())
    return h.digest()


# ---------------------------------------------------------------- paket JSON (tidak berubah)
def buat_paket(kombinasi, sig_ecdsa, sig_pqc):
    """Menggabungkan nama kombinasi dan dua tanda tangan menjadi satu teks JSON."""
    return json.dumps(
        {
            "versi": VERSI_PAKET,
            "kombinasi": kombinasi,
            "sig_ecdsa": base64.b64encode(sig_ecdsa).decode("ascii"),
            "sig_pqc": base64.b64encode(sig_pqc).decode("ascii"),
        },
        separators=(",", ":"),
    )


def urai_paket(teks):
    """Memecah paket menjadi (kombinasi, sig_ecdsa, sig_pqc). Error kalau paket tidak lengkap."""
    data = json.loads(teks)
    for kolom in ("kombinasi", "sig_ecdsa", "sig_pqc"):
        if kolom not in data or not data[kolom]:
            raise ValueError(f"Paket tidak lengkap: {kolom} tidak ada")
    return (
        data["kombinasi"],
        base64.b64decode(data["sig_ecdsa"], validate=True),
        base64.b64decode(data["sig_pqc"], validate=True),
    )


# ---------------------------------------------------------------- segmen JPEG
def _pecah_segmen_awal(data):
    """Memecah bagian awal file JPEG menjadi: segmen APPn/COM di depan, dan sisa file.

    Mengembalikan (daftar_segmen, posisi_sisa). Setiap segmen berupa tuple (penanda, isi).
    Pembacaan berhenti di segmen pertama yang bukan APPn/COM (mis. tabel kuantisasi),
    karena paket selalu disisipkan di bagian depan ini.
    """
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        raise ValueError("Bukan file JPEG")
    segmen, i = [], 2
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            raise ValueError("Struktur JPEG tidak dikenali")
        while data[i + 1] == 0xFF:                 # byte pengisi FF yang boleh berulang
            i += 1
        penanda = data[i + 1]
        if not (0xE0 <= penanda <= 0xEF or penanda == 0xFE):
            break
        panjang = struct.unpack(">H", data[i + 2:i + 4])[0]
        if panjang < 2 or i + 2 + panjang > len(data):
            raise ValueError("Panjang segmen JPEG tidak valid")
        segmen.append((penanda, data[i + 4:i + 2 + panjang]))
        i += 2 + panjang
    return segmen, i


def _segmen_kita(penanda, isi):
    return penanda == PENANDA_SEGMEN and isi.startswith(ID_SEGMEN)


def _buat_segmen(penanda, isi):
    return b"\xff" + bytes([penanda]) + struct.pack(">H", len(isi) + 2) + isi


def sisipkan_paket(data_jpeg, paket=None):
    """Mengembalikan byte JPEG baru: segmen paket lama dibuang, lalu paket baru (bila ada) disisipkan.

    Data gambar tidak didekode dan tidak dikompres ulang, sehingga piksel tidak berubah.
    paket=None berarti hanya membuang paket (menghasilkan JPEG tanpa tanda tangan).
    """
    segmen, posisi_sisa = _pecah_segmen_awal(data_jpeg)
    bawaan = [_buat_segmen(p, isi) for p, isi in segmen if not _segmen_kita(p, isi)]

    baru = []
    if paket is not None:
        isi_paket = paket.encode("utf-8")
        potongan = [isi_paket[k:k + MAKS_POTONGAN] for k in range(0, len(isi_paket), MAKS_POTONGAN)] or [b""]
        if len(potongan) > 255:
            raise ValueError("Paket terlalu besar untuk disisipkan ke JPEG")
        for nomor, bagian in enumerate(potongan, 1):
            baru.append(_buat_segmen(PENANDA_SEGMEN, ID_SEGMEN + bytes([nomor, len(potongan)]) + bagian))

    return b"\xff\xd8" + b"".join(bawaan) + b"".join(baru) + data_jpeg[posisi_sisa:]


def _baca_paket_dari_byte(data):
    """Membaca dan menggabungkan potongan paket. None bila tidak ada segmen paket."""
    try:
        segmen, _ = _pecah_segmen_awal(data)
    except ValueError:
        return None
    bagian, jumlah = {}, None
    for p, isi in segmen:
        if _segmen_kita(p, isi) and len(isi) >= len(ID_SEGMEN) + 2:
            nomor, total = isi[len(ID_SEGMEN)], isi[len(ID_SEGMEN) + 1]
            bagian[nomor] = isi[len(ID_SEGMEN) + 2:]
            jumlah = total
    if not bagian:
        return None
    # Kalau ada bagian yang hilang, hasil gabungan tidak utuh sehingga urai_paket akan gagal
    # (dianggap paket rusak/tidak lengkap, kondisi 1b).
    gabungan = b"".join(bagian[n] for n in range(1, (jumlah or 0) + 1) if n in bagian)
    return gabungan.decode("utf-8", errors="replace")


# ---------------------------------------------------------------- dipakai modul lain
def simpan_citra(img, paket=None):
    """Menghasilkan byte file JPEG dari citra yang dibuka dengan buka_citra(), berisi paket (bila ada).

    Hanya citra yang masih punya byte JPEG aslinya yang bisa disimpan, karena gambar
    tidak boleh dikompres ulang (piksel akan berubah).
    """
    data = getattr(img, "berkas_jpeg", None)
    if data is None:
        raise ValueError("Citra tidak memiliki byte JPEG asli; tidak bisa disimpan tanpa kompres ulang.")
    return sisipkan_paket(data, paket)


def lampirkan_paket(img, paket):
    """Untuk citra hasil manipulasi piksel yang hanya ada di memori (tidak dijadikan file).

    Citra hasil manipulasi piksel sengaja TIDAK disimpan ulang sebagai JPEG, karena kompresi
    JPEG akan mengubah piksel lain di luar manipulasi yang diuji. Paket aslinya dilampirkan
    apa adanya, sehingga yang diuji hanya perubahan pikselnya.
    """
    img.paket_terlampir = paket
    return img


def baca_paket(img):
    """Membaca paket tanda tangan dari citra. Hasilnya None kalau tidak ditemukan."""
    if hasattr(img, "paket_terlampir"):
        return img.paket_terlampir
    data = getattr(img, "berkas_jpeg", None)
    return _baca_paket_dari_byte(data) if data is not None else None


def ukuran_tanpa_paket(img):
    """Ukuran file JPEG (byte) setelah segmen paket dibuang, sebagai pembanding pertambahan ukuran."""
    return len(simpan_citra(img, None))