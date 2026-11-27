"""Pengujian pendukung: apakah 10 citra per kategori cukup, atau perlu 30?

Cara kerja:
  1. Untuk beberapa kombinasi, ke-90 citra sampel (30 per kategori) diukur seperti pada
     uji_kinerja.py: 1 pemanasan per kombinasi, 10 pengulangan per citra, lalu diringkas
     menjadi 1 nilai rata-rata per citra.
  2. Untuk setiap kategori, dihitung rata-rata dari ke-30 citra (acuan).
  3. Lalu diambil 1.000 kali secara acak 10 citra dari 30 citra itu (seed tetap),
     dan dihitung rata-rata dari setiap kelompok 10 citra.
  4. Dibandingkan: seberapa jauh rata-rata "10 citra" bisa menyimpang dari rata-rata "30 citra".
     Kalau simpangannya kecil, 10 citra sudah cukup; kalau besar, 30 citra lebih aman.

Cara pakai (WSL, venv-wsl aktif, dari folder proyek):
    python banding_jumlah_sampel.py                 # 3 kombinasi bawaan
    python banding_jumlah_sampel.py ECDSA-P256+ML-DSA-44 ECDSA-P256+Falcon-512

Kalau terhenti, jalankan lagi: kombinasi yang datanya sudah lengkap dilewati.

Hasil (folder hasil_jumlah_sampel/):
  mentah_<kode>.csv            data mentah per pengukuran
  ringkasan_jumlah_sampel.csv  perbandingan 10 vs 30 citra per kombinasi, kategori, metrik
  ringkasan_jumlah_sampel.xlsx isi yang sama dalam Excel (bila openpyxl terpasang)

Catatan: ini pengujian pendukung untuk menjawab pertanyaan jumlah sampel,
bukan pengganti pengujian kinerja utama.
"""

import csv
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import uji_kinerja as uk
from core import citra
from core.kombinasi import KOMBINASI

SEED = 42
ULANG = 10
N_KECIL = 10            # ukuran kelompok kecil yang diuji
JUMLAH_ACAK = 1000      # berapa kali kelompok 10 citra diambil secara acak
FOLDER = Path("hasil_jumlah_sampel")

KOMBINASI_BAWAAN = ["ECDSA-P256+ML-DSA-44", "ECDSA-P256+Falcon-512", "ECDSA-P256+SLH-DSA-SHA2-128f"]

# Metrik yang dibandingkan: dua yang bergantung pada citra, dua yang bergantung pada algoritma
METRIK = ["waktu_hash_ms", "waktu_ttd_pqc_ms", "waktu_verifikasi_total_ms", "pertambahan_file_byte"]


def ukur_kombinasi(kode, sampel):
    """Mengukur 90 citra x ULANG untuk satu kombinasi. Mengembalikan daftar baris mentah."""
    path = FOLDER / f"mentah_{uk.nama_file(kode)}.csv"
    target = len(sampel) * ULANG
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            lama = list(csv.DictReader(f))
        if len(lama) >= target:
            print(f"  {kode}: sudah lengkap, dilewati")
            return lama

    print(f"  {kode}: mengukur {target} pengukuran ...", flush=True)
    uk.satu_pengukuran(citra.buka_citra(str(uk.path_citra(sampel[0]))), kode)   # pemanasan
    baris = []
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=uk.KOLOM)
        w.writeheader()
        for d in sampel:
            img = citra.buka_citra(str(uk.path_citra(d)))
            for r in range(1, ULANG + 1):
                kunci, wk, info, hasil = uk.satu_pengukuran(img, kode)
                b = uk.susun_baris(kode, d, r, kunci, wk, info, hasil)
                w.writerow(b)
                baris.append({k: str(v) for k, v in b.items()})
            f.flush()
    return baris


def per_citra(baris):
    """10 pengulangan -> 1 nilai rata-rata per citra, dikelompokkan per kategori."""
    grup = defaultdict(list)
    for b in baris:
        grup[(b["kategori"], b["citra"])].append(b)
    hasil = defaultdict(lambda: defaultdict(list))     # kategori -> metrik -> [nilai per citra]
    for (kategori, _), daftar in grup.items():
        for m in METRIK:
            nilai = [float(b[m]) for b in daftar if b[m] not in ("", None)]
            if nilai:
                hasil[kategori][m].append(statistics.fmean(nilai))
    return hasil


def bandingkan(nilai_30, rng):
    """Membandingkan rata-rata 30 citra dengan rata-rata banyak kelompok acak 10 citra."""
    rata_30 = statistics.fmean(nilai_30)
    sd_30 = statistics.stdev(nilai_30)
    rata_10 = sorted(statistics.fmean(rng.sample(nilai_30, N_KECIL)) for _ in range(JUMLAH_ACAK))
    bawah = rata_10[int(0.025 * JUMLAH_ACAK)]
    atas = rata_10[int(0.975 * JUMLAH_ACAK) - 1]
    simpang = max(abs(x - rata_30) for x in rata_10)
    return {
        "n_citra": len(nilai_30),
        "rata_30_citra": rata_30,
        "sd_30_citra": sd_30,
        "galat_baku_n30": sd_30 / math.sqrt(len(nilai_30)),
        "galat_baku_n10": sd_30 / math.sqrt(N_KECIL),
        "rata_10_citra_min": rata_10[0],
        "rata_10_citra_maks": rata_10[-1],
        "rata_10_citra_p2_5": bawah,
        "rata_10_citra_p97_5": atas,
        "simpangan_maks_10_thd_30_persen": (100 * simpang / rata_30) if rata_30 else 0.0,
        "rentang_95_10_citra_persen": (100 * (atas - bawah) / rata_30) if rata_30 else 0.0,
    }


def jalankan(daftar_kode):
    for kode in daftar_kode:
        if kode not in KOMBINASI:
            sys.exit(f"Kombinasi tidak dikenal: {kode}")
    FOLDER.mkdir(exist_ok=True)
    sampel = uk.baca_sampel()
    print(f"{len(sampel)} citra x {ULANG} pengulangan x {len(daftar_kode)} kombinasi\n")

    ringkasan = []
    for kode in daftar_kode:
        data = per_citra(ukur_kombinasi(kode, sampel))
        for kategori in uk.urutan_kategori() or sorted(data):
            for m in METRIK:
                nilai = data[kategori][m]
                if len(nilai) <= N_KECIL:
                    continue
                rng = random.Random(f"{SEED}:{kode}:{kategori}:{m}")
                ringkasan.append({"kode": kode, "kategori": kategori, "metrik": m, **bandingkan(nilai, rng)})

    kolom = list(ringkasan[0].keys())
    for b in ringkasan:
        for k, v in b.items():
            if isinstance(v, float):
                b[k] = round(v, 6)
    uk.tulis_csv(FOLDER / "ringkasan_jumlah_sampel.csv", kolom, ringkasan)
    uk.tulis_xlsx(FOLDER / "ringkasan_jumlah_sampel.xlsx", {"ringkasan": (kolom, ringkasan)})

    print("\n=== Simpangan rata-rata 10 citra terhadap rata-rata 30 citra ===")
    print(f"{'kombinasi':32} {'kategori':9} {'metrik':28} {'maks %':>8} {'rentang95 %':>12}")
    for b in ringkasan:
        print(f"{b['kode']:32} {b['kategori']:9} {b['metrik']:28} "
              f"{b['simpangan_maks_10_thd_30_persen']:8.2f} {b['rentang_95_10_citra_persen']:12.2f}")
    print(f"\nRincian: {FOLDER}/ringkasan_jumlah_sampel.csv (dan .xlsx)")
    print("maks %      = simpangan terbesar rata-rata 10 citra dari rata-rata 30 citra")
    print("rentang95 % = lebar rentang tempat 95% rata-rata 10 citra berada, dibanding rata-rata 30 citra")


if __name__ == "__main__":
    jalankan(sys.argv[1:] or KOMBINASI_BAWAAN)