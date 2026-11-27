"""Membandingkan dua cara menyimpan tanda tangan: PNG (cara lama) vs JPEG (cara sekarang).

Untuk setiap citra sampel, hash yang sama ditandatangani satu kali, lalu paket yang sama
disimpan dengan dua cara:
  - PNG : citra disimpan ulang sebagai PNG, paket di chunk tEXt "HybridSignature" (cara lama)
  - JPEG: paket disisipkan ke segmen APP15 file JPEG asli, tanpa kompres ulang (core/citra.py)

Yang dicatat per citra:
  - apakah hash piksel setelah disimpan tetap sama dengan hash citra asli
  - apakah hasil verifikasi VALID
  - ukuran file asli, ukuran PNG bertanda, ukuran JPEG bertanda (byte)
  - waktu penyimpanan (median dari beberapa kali ulang, ms)
  - format file hasil

Cara pakai (WSL, venv-wsl aktif, dari folder proyek):
    python banding_png_jpeg.py            # 3 citra per kategori (9 citra), kombinasi pertama
    python banding_png_jpeg.py 30         # 30 citra per kategori (90 citra)
    python banding_png_jpeg.py 3 ECDSA-P256+ML-DSA-44

Hasil: hasil_banding_png_jpeg.csv + ringkasan di terminal.
Catatan: ini pengujian pendukung untuk menjawab pertanyaan "PNG atau JPEG", bukan bagian
dari pengujian kinerja utama.
"""

import csv
import io
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

from PIL import Image, PngImagePlugin

from core import citra, hybrid
from core.kombinasi import KOMBINASI

ULANG_WAKTU = 5


def simpan_png_lama(img, paket):
    """Cara lama: citra disimpan ulang sebagai PNG, paket di chunk tEXt."""
    meta = PngImagePlugin.PngInfo()
    meta.add_text(citra.KUNCI_METADATA, paket)
    buf = io.BytesIO()
    img.save(buf, format="PNG", pnginfo=meta)
    return buf.getvalue()


def baca_paket_png(data):
    img = Image.open(io.BytesIO(data))
    img.load()
    return img, (getattr(img, "text", {}) or {}).get(citra.KUNCI_METADATA)


def cek_valid(img, paket, kunci_publik):
    if paket is None:
        return False
    _, sig_e, sig_p = citra.urai_paket(paket)
    return hybrid.verifikasi(citra.hitung_hash(img), sig_e, sig_p, kunci_publik)["valid"]


def median_ms(fungsi):
    hasil = []
    for _ in range(ULANG_WAKTU):
        t0 = time.perf_counter()
        keluaran = fungsi()
        hasil.append((time.perf_counter() - t0) * 1000)
    return statistics.median(hasil), keluaran


def pilih_sampel(per_kategori):
    with open("sampel_90.csv", encoding="utf-8") as f:
        data = list(csv.DictReader(f))
    hitung, pilih = defaultdict(int), []
    for d in data:
        if hitung[d["kategori"]] < per_kategori:
            pilih.append(d)
            hitung[d["kategori"]] += 1
    return pilih


def jalankan(per_kategori=3, kombinasi=None):
    kombinasi = kombinasi or next(iter(KOMBINASI))
    if kombinasi not in KOMBINASI:
        sys.exit(f"Kombinasi tidak dikenal: {kombinasi}")
    kunci = hybrid.bangkitkan_kunci(kombinasi)
    kunci_publik = hybrid.kunci_publik_dari(kunci)
    sampel = pilih_sampel(per_kategori)
    print(f"Kombinasi: {kombinasi} | {len(sampel)} citra\n")

    baris = []
    for d in sampel:
        path = Path("sampel") / d["kategori"] / Path(d["file"]).name
        img = citra.buka_citra(str(path))
        hash_asli = citra.hitung_hash(img)
        sig_e, sig_p = hybrid.tandatangani(hash_asli, kunci)
        paket = citra.buat_paket(kombinasi, sig_e, sig_p)

        ms_png, data_png = median_ms(lambda: simpan_png_lama(img, paket))
        ms_jpg, data_jpg = median_ms(lambda: citra.simpan_citra(img, paket))

        img_png, paket_png = baca_paket_png(data_png)
        img_jpg = citra.buka_citra(data_jpg)

        ukuran_asli = citra.ukuran_tanpa_paket(img)
        baris.append({
            "citra": path.name, "kategori": d["kategori"], "mode": img.mode,
            "ukuran_asli_jpeg_byte": ukuran_asli,
            "ukuran_png_bertanda_byte": len(data_png),
            "ukuran_jpeg_bertanda_byte": len(data_jpg),
            "rasio_png_thd_asli": round(len(data_png) / ukuran_asli, 3),
            "rasio_jpeg_thd_asli": round(len(data_jpg) / ukuran_asli, 3),
            "hash_sama_png": citra.hitung_hash(img_png) == hash_asli,
            "hash_sama_jpeg": citra.hitung_hash(img_jpg) == hash_asli,
            "valid_png": cek_valid(img_png, paket_png, kunci_publik),
            "valid_jpeg": cek_valid(img_jpg, citra.baca_paket(img_jpg), kunci_publik),
            "format_hasil_png": img_png.format, "format_hasil_jpeg": img_jpg.format,
            "waktu_simpan_png_ms": round(ms_png, 4),
            "waktu_simpan_jpeg_ms": round(ms_jpg, 4),
        })
        print(f"  {path.name:40} selesai", flush=True)

    with open("hasil_banding_png_jpeg.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(baris[0].keys()))
        w.writeheader()
        w.writerows(baris)

    def med(kolom):
        return statistics.median(b[kolom] for b in baris)

    print("\n=== Ringkasan (median dari semua citra) ===")
    print(f"{'':28} {'PNG (lama)':>14} {'JPEG (sekarang)':>16}")
    print(f"{'Hash sama dengan asli':28} {sum(b['hash_sama_png'] for b in baris):>10}/{len(baris):<3} "
          f"{sum(b['hash_sama_jpeg'] for b in baris):>12}/{len(baris):<3}")
    print(f"{'Verifikasi VALID':28} {sum(b['valid_png'] for b in baris):>10}/{len(baris):<3} "
          f"{sum(b['valid_jpeg'] for b in baris):>12}/{len(baris):<3}")
    print(f"{'Format file hasil':28} {'PNG':>14} {'JPEG':>16}")
    print(f"{'Ukuran file asli (byte)':28} {med('ukuran_asli_jpeg_byte'):>14,.0f} {med('ukuran_asli_jpeg_byte'):>16,.0f}")
    print(f"{'Ukuran bertanda (byte)':28} {med('ukuran_png_bertanda_byte'):>14,.0f} {med('ukuran_jpeg_bertanda_byte'):>16,.0f}")
    print(f"{'Rasio terhadap asli':28} {med('rasio_png_thd_asli'):>14.3f} {med('rasio_jpeg_thd_asli'):>16.3f}")
    print(f"{'Waktu simpan (ms)':28} {med('waktu_simpan_png_ms'):>14.3f} {med('waktu_simpan_jpeg_ms'):>16.3f}")
    print("\nRincian per citra: hasil_banding_png_jpeg.csv")


if __name__ == "__main__":
    a = sys.argv[1:]
    jalankan(int(a[0]) if a else 3, a[1] if len(a) > 1 else None)