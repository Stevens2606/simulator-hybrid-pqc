"""Pengujian kinerja (subbab 3.8.4) pada 90 citra sampel.

Untuk setiap kombinasi hybrid, setiap citra, dan setiap pengulangan:
  1. bangkitkan pasangan kunci  -> waktu pembangkitan kunci
  2. tandatangani citra         -> waktu penandatanganan, memori, ukuran tanda tangan & file
  3. verifikasi citra           -> waktu verifikasi, memori
Pengukuran dilakukan dalam dua putaran:
  - putaran waktu  : tanpa pelacak memori, agar waktu tidak terganggu
  - putaran memori : memori puncak diukur dengan tracemalloc (bawaan Python)
Sebelum pengukuran, setiap kombinasi dijalankan 1 kali sebagai pemanasan (tidak dicatat).

Cara pakai (di WSL, venv-wsl aktif, dari folder simulator_hybrid):
    python uji_kinerja.py              # lengkap: 90 citra x 10 pengulangan
    python uji_kinerja.py 3 2          # uji coba cepat: 3 citra x 2 pengulangan

Hasil:
  - hasil_uji_kinerja.csv  (satu baris per pengukuran, ditulis bertahap)
  - ringkasan rata-rata dan standar deviasi di terminal
"""

import csv
import statistics
import sys
import time
import tracemalloc
from collections import defaultdict
from pathlib import Path

from cryptography.hazmat.primitives import serialization

from core import citra, hybrid, proses
from core.kombinasi import KOMBINASI

ULANG_DEFAULT = 10


def status_dari(hasil):
    if "status" in hasil:
        return hasil["status"]
    return "VALID" if hasil.get("valid") else "TIDAK VALID"


def ukuran(obj):
    """Ukuran kunci dalam byte, baik berupa bytes maupun objek kunci ECDSA."""
    if isinstance(obj, (bytes, bytearray)):
        return len(obj)
    if hasattr(obj, "private_numbers"):            # kunci privat ECDSA
        return (obj.curve.key_size + 7) // 8
    if hasattr(obj, "public_bytes"):               # kunci publik ECDSA
        return len(obj.public_bytes(serialization.Encoding.X962,
                                    serialization.PublicFormat.UncompressedPoint))
    return ""


def ukuran_kunci(kunci):
    ambil = (lambda n: kunci[n]) if isinstance(kunci, dict) else (lambda n: getattr(kunci, n, None))
    hasil = {}
    for nama, kandidat in (("ecdsa_publik", ["ecdsa_publik", "ecdsa_publik_bytes"]),
                           ("ecdsa_privat", ["ecdsa_privat"]),
                           ("pqc_publik", ["pqc_publik"]),
                           ("pqc_privat", ["pqc_privat"])):
        nilai = ""
        for k in kandidat:
            try:
                obj = ambil(k)
            except (KeyError, TypeError):
                obj = None
            if obj is not None:
                nilai = ukuran(obj)
                break
        hasil[f"kunci_{nama}_byte"] = nilai
    return hasil


def baca_sampel(batas=None):
    with open("sampel_90.csv", encoding="utf-8") as f:
        data = list(csv.DictReader(f))
    return data[:batas] if batas else data


def ukur_memori(img, kombinasi):
    """Memori puncak (KB) saat penandatanganan dan saat verifikasi, diukur dengan tracemalloc."""
    kunci, _ = proses.ukur_keygen(kombinasi)
    kunci_publik = {kombinasi: hybrid.kunci_publik_dari(kunci)}
    tracemalloc.start()
    tracemalloc.reset_peak()
    png, _ = proses.tandatangani_citra(img, kunci)
    puncak_ttd = tracemalloc.get_traced_memory()[1]
    img_ttd = citra.buka_citra(png)
    tracemalloc.reset_peak()
    awal = tracemalloc.get_traced_memory()[0]
    proses.verifikasi_citra(img_ttd, kunci_publik)
    puncak_ver = tracemalloc.get_traced_memory()[1] - awal
    tracemalloc.stop()
    return puncak_ttd / 1024, puncak_ver / 1024


def satu_putaran(img, kombinasi):
    kunci, waktu_keygen = proses.ukur_keygen(kombinasi)
    png, info = proses.tandatangani_citra(img, kunci)
    kunci_publik = {kombinasi: hybrid.kunci_publik_dari(kunci)}
    hasil = proses.verifikasi_citra(citra.buka_citra(png), kunci_publik)
    return kunci, waktu_keygen, info, hasil


def jalankan(batas=None, ulang=ULANG_DEFAULT):
    sampel = baca_sampel(batas)
    total = len(KOMBINASI) * len(sampel) * ulang
    print(f"{len(sampel)} citra x {ulang} pengulangan x {len(KOMBINASI)} kombinasi = {total} pengukuran\n")

    kolom = None
    rekap = defaultdict(lambda: defaultdict(list))    # (kombinasi, kategori) -> metrik -> nilai
    mulai, selesai, tidak_valid = time.time(), 0, 0

    with open("hasil_uji_kinerja.csv", "w", newline="", encoding="utf-8") as f:
        for kombinasi in KOMBINASI:
            # pemanasan: 1 kali, tidak dicatat
            satu_putaran(citra.buka_citra(str(Path("sampel") / sampel[0]["kategori"]
                                              / Path(sampel[0]["file"]).name)), kombinasi)
            for d in sampel:
                img = citra.buka_citra(str(Path("sampel") / d["kategori"] / Path(d["file"]).name))
                for r in range(1, ulang + 1):
                    kunci, t_keygen, info, hasil = satu_putaran(img, kombinasi)
                    mem_ttd, mem_ver = ukur_memori(img, kombinasi)   # putaran memori (terpisah)
                    baris = {
                        "kombinasi": kombinasi, "citra": Path(d["file"]).name,
                        "kategori": d["kategori"], "piksel": d["piksel"], "mode": d["mode"],
                        "ulangan": r, "status_verifikasi": status_dari(hasil),
                        "waktu_keygen_ms": round(t_keygen, 4),
                        "waktu_hash_ms": round(info.get("waktu_hash_ms", 0), 4),
                        "waktu_ttd_saja_ms": round(info.get("waktu_tanda_tangan_ms", 0), 4),
                        "waktu_simpan_ms": round(info.get("waktu_simpan_ms", 0), 4),
                        "waktu_penandatanganan_ms": round(info.get("waktu_total_ms", 0), 4),
                        "waktu_verifikasi_ms": round(hasil.get("waktu_verifikasi_ms", 0), 4),
                        "memori_puncak_ttd_kb": round(mem_ttd, 2),
                        "memori_puncak_verifikasi_kb": round(mem_ver, 2),
                        "sig_ecdsa_byte": info.get("ukuran_sig_ecdsa", ""),
                        "sig_pqc_byte": info.get("ukuran_sig_pqc", ""),
                        "paket_byte": info.get("ukuran_paket", ""),
                        "png_polos_byte": info.get("ukuran_png_polos", ""),
                        "png_bertanda_byte": info.get("ukuran_png_bertanda", ""),
                        "pertambahan_file_byte": info.get("pertambahan_file", ""),
                        **ukuran_kunci(kunci),
                    }
                    if kolom is None:
                        kolom = list(baris.keys())
                        w = csv.DictWriter(f, fieldnames=kolom)
                        w.writeheader()
                    w.writerow(baris)
                    f.flush()
                    for m in ("waktu_keygen_ms", "waktu_ttd_saja_ms", "waktu_penandatanganan_ms",
                              "waktu_verifikasi_ms", "memori_puncak_ttd_kb",
                              "memori_puncak_verifikasi_kb", "sig_pqc_byte",
                              "pertambahan_file_byte"):
                        if baris[m] != "":
                            rekap[(kombinasi, d["kategori"])][m].append(float(baris[m]))
                    selesai += 1
                    tidak_valid += baris["status_verifikasi"] != "VALID"
                    if selesai % 50 == 0 or selesai == total:
                        lalu = time.time() - mulai
                        sisa = lalu / selesai * (total - selesai)
                        print(f"  {selesai}/{total} pengukuran | berjalan {lalu / 60:.1f} menit | "
                              f"perkiraan sisa {sisa / 60:.1f} menit", flush=True)

    print(f"\nSelesai dalam {(time.time() - mulai) / 60:.1f} menit. Rincian: hasil_uji_kinerja.csv\n")
    print("=== Rata-rata ± standar deviasi per kombinasi dan kategori ===")
    for (kombinasi, kategori), metrik in rekap.items():
        print(f"\n{kombinasi} | {kategori}")
        for m, nilai in metrik.items():
            sd = statistics.stdev(nilai) if len(nilai) > 1 else 0.0
            print(f"  {m:26} {statistics.mean(nilai):12.3f} ± {sd:10.3f}  (n={len(nilai)})")
    if tidak_valid:
        print(f"\nPERINGATAN: {tidak_valid} verifikasi tidak VALID, cek kolom status_verifikasi di CSV")
    else:
        print("\nSemua verifikasi pada pengujian kinerja berstatus VALID.")


if __name__ == "__main__":
    a = sys.argv[1:]
    jalankan(int(a[0]) if a else None, int(a[1]) if len(a) > 1 else ULANG_DEFAULT)