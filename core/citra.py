# Pengolahan citra: membaca piksel, menghitung hash,
# serta menyimpan dan membaca paket tanda tangan di metadata PNG.

import base64
import hashlib
import io
import json

from PIL import Image, PngImagePlugin

KUNCI_METADATA = "HybridSignature"
VERSI_PAKET = 1


def buka_citra(sumber):
    """Membuka citra dari path file atau dari bytes, lalu memuat nilai pikselnya."""
    if isinstance(sumber, (bytes, bytearray)):
        sumber = io.BytesIO(sumber)
    img = Image.open(sumber)
    img.load()
    return img


def hitung_hash(img):
    """SHA-256 dari lebar, tinggi, dan nilai piksel citra (hasilnya 32 byte)."""
    lebar, tinggi = img.size
    h = hashlib.sha256()
    h.update(lebar.to_bytes(4, "big"))
    h.update(tinggi.to_bytes(4, "big"))
    h.update(img.tobytes())
    return h.digest()


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


def simpan_png(img, paket=None):
    """Menyimpan citra sebagai PNG. Kalau ada paket, paket disisipkan ke metadata."""
    meta = PngImagePlugin.PngInfo()
    if paket is not None:
        meta.add_text(KUNCI_METADATA, paket)
    buf = io.BytesIO()
    img.save(buf, format="PNG", pnginfo=meta)
    return buf.getvalue()


def baca_paket(img):
    """Membaca paket tanda tangan dari metadata. Hasilnya None kalau tidak ditemukan."""
    teks = getattr(img, "text", {}) or {}
    return teks.get(KUNCI_METADATA)