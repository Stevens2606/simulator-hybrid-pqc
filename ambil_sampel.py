"""Mengambil 90 citra sampel: 30 citra acak dari setiap kategori resolusi (seed 42).

Untuk subbab 3.4.3. Membutuhkan dataset_kategori.csv hasil kategori_dataset.py.
Hasil:
  - ringkasan komposisi sampel di terminal
  - sampel_90.csv          (daftar 90 citra sampel, dipakai oleh script pengujian)
  - folder sampel/         (salinan 90 citra sampel, nama file asli dipertahankan)

Cara pakai (di WSL, venv-wsl aktif, dari folder simulator_hybrid):
    python ambil_sampel.py
"""

import csv
import random
import shutil
from pathlib import Path

SEED = 42
PER_KATEGORI = 30
KATEGORI = ["Kecil", "Sedang", "Besar"]

KANDIDAT = [Path("/mnt/d/Perkuliahan/TA/dataset/chest_xray"),
            Path(r"D:\Perkuliahan\TA\dataset\chest_xray")]
DATASET = next((p for p in KANDIDAT if p.exists()), None)
if DATASET is None:
    raise SystemExit("Folder dataset tidak ditemukan. Ubah isi KANDIDAT sesuai lokasi dataset.")
if not Path("dataset_kategori.csv").exists():
    raise SystemExit("dataset_kategori.csv belum ada. Jalankan dulu: python kategori_dataset.py")


def angka(n):
    return f"{n:,}".replace(",", ".")


with open("dataset_kategori.csv", encoding="utf-8") as f:
    semua = list(csv.DictReader(f))

# Satu generator acak dengan seed tetap, dipakai berurutan Kecil -> Sedang -> Besar,
# sehingga sampel yang terpilih selalu sama setiap kali script dijalankan.
rng = random.Random(SEED)
sampel = []
for k in KATEGORI:
    kelompok = sorted((d for d in semua if d["kategori"] == k), key=lambda d: d["file"])
    terpilih = sorted(rng.sample(kelompok, PER_KATEGORI), key=lambda d: int(d["piksel"]))
    sampel.extend(terpilih)

# Ringkasan komposisi
print(f"Seed: {SEED}, {PER_KATEGORI} citra per kategori, total {len(sampel)} citra\n")
print(f"{'Kategori':8s} | {'NORMAL':>6s} {'PNEU':>5s} | {'L':>3s} {'RGB':>4s} | "
      f"{'Jumlah piksel (min - maks)':27s} | {'Rata-rata piksel':>16s} | Ukuran file (KB)")
for k in KATEGORI:
    g = [d for d in sampel if d["kategori"] == k]
    px = [int(d["piksel"]) for d in g]
    kb = [float(d["ukuran_kb"]) for d in g]
    nn = sum(d["kelas"] == "NORMAL" for d in g)
    rgb = sum(d["mode"] == "RGB" for d in g)
    print(f"{k:8s} | {nn:6d} {len(g) - nn:5d} | {len(g) - rgb:3d} {rgb:4d} | "
          f"{angka(min(px)):>11s} - {angka(max(px)):>13s} | {angka(round(sum(px) / len(px))):>16s} | "
          f"{min(kb):.2f} - {max(kb):.2f}")
nn = sum(d["kelas"] == "NORMAL" for d in sampel)
rgb = sum(d["mode"] == "RGB" for d in sampel)
print(f"{'Total':8s} | {nn:6d} {len(sampel) - nn:5d} | {len(sampel) - rgb:3d} {rgb:4d} |")

# Simpan daftar sampel
with open("sampel_90.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["no"] + list(sampel[0].keys()))
    w.writeheader()
    for i, d in enumerate(sampel, 1):
        w.writerow({"no": i, **d})
print("\nTersimpan: sampel_90.csv")

# Salin citra sampel ke folder sampel/<kategori>/
for d in sampel:
    tujuan = Path("sampel") / d["kategori"]
    tujuan.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DATASET / d["file"], tujuan / Path(d["file"]).name)
print("Tersalin: 90 citra ke folder sampel/Kecil, sampel/Sedang, sampel/Besar")