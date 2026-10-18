"""Analisis struktur dataset Chest X-Ray Images (Pneumonia) untuk subbab 3.4.1.

Menghitung jumlah citra per folder (train/test/val) dan per kelas (NORMAL/PNEUMONIA),
format file, mode warna, serta file lain yang bukan citra.

Cara pakai (di WSL, venv-wsl aktif, dari folder simulator_hybrid):
    python analisis_dataset.py
"""

from collections import Counter
from pathlib import Path

from PIL import Image

KANDIDAT = [Path("/mnt/d/Perkuliahan/TA/dataset/chest_xray"),
            Path(r"D:\Perkuliahan\TA\dataset\chest_xray")]
DATASET = next((p for p in KANDIDAT if p.exists()), None)
if DATASET is None:
    raise SystemExit("Folder dataset tidak ditemukan. Ubah isi KANDIDAT sesuai lokasi dataset.")

FOLDER = ["train", "test", "val"]
KELAS = ["NORMAL", "PNEUMONIA"]
EKSTENSI_CITRA = {".jpeg", ".jpg", ".png"}

jumlah = {}                  # (folder, kelas) -> jumlah citra
mode_per_kelas = {k: Counter() for k in KELAS}
format_file = Counter()
bukan_citra = []

for f in FOLDER:
    for k in KELAS:
        n = 0
        for p in sorted((DATASET / f / k).iterdir()):
            if p.suffix.lower() not in EKSTENSI_CITRA:
                bukan_citra.append(str(p.relative_to(DATASET)))
                continue
            with Image.open(p) as img:
                mode_per_kelas[k][img.mode] += 1
                format_file[img.format] += 1
            n += 1
        jumlah[(f, k)] = n

# File lain di luar subfolder kelas (misalnya .DS_Store)
for p in DATASET.rglob("*"):
    if p.is_file() and p.suffix.lower() not in EKSTENSI_CITRA:
        r = str(p.relative_to(DATASET))
        if r not in bukan_citra:
            bukan_citra.append(r)

print("=== Jumlah citra per folder dan kelas ===")
print(f"{'Folder':8s} {'NORMAL':>8s} {'PNEUMONIA':>10s} {'Jumlah':>8s}")
for f in FOLDER:
    a, b = jumlah[(f, "NORMAL")], jumlah[(f, "PNEUMONIA")]
    print(f"{f:8s} {a:8d} {b:10d} {a + b:8d}")
tn = sum(jumlah[(f, "NORMAL")] for f in FOLDER)
tp = sum(jumlah[(f, "PNEUMONIA")] for f in FOLDER)
print(f"{'Total':8s} {tn:8d} {tp:10d} {tn + tp:8d}")

print("\n=== Format file (dibaca dari isi file, bukan nama) ===")
for k, v in format_file.items():
    print(f"{k}: {v}")

print("\n=== Mode warna per kelas ===")
print("(L = grayscale 8-bit, RGB = 3 kanal warna)")
for k in KELAS:
    print(f"{k:10s} " + ", ".join(f"{m}: {n}" for m, n in sorted(mode_per_kelas[k].items())))

print("\n=== File yang bukan citra ===")
print(f"Jumlah: {len(bukan_citra)}")
for r in bukan_citra:
    print("  " + r)