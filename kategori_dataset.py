"""Membagi seluruh citra dataset ke kategori Kecil, Sedang, Besar berdasarkan jumlah piksel (tertil).

Untuk subbab 3.4.2. Hasil:
  - tabel distribusi di terminal
  - dataset_kategori.csv  (daftar seluruh citra + kategorinya, dipakai lagi saat pengambilan sampel)
  - Gambar_3.6_Distribusi_Resolusi.png

Cara pakai (di WSL, venv-wsl aktif, dari folder simulator_hybrid):
    python kategori_dataset.py
"""

import csv
from pathlib import Path

import matplotlib.pyplot as plt
from PIL import Image

KANDIDAT = [Path("/mnt/d/Perkuliahan/TA/dataset/chest_xray"),
            Path(r"D:\Perkuliahan\TA\dataset\chest_xray")]
DATASET = next((p for p in KANDIDAT if p.exists()), None)
if DATASET is None:
    raise SystemExit("Folder dataset tidak ditemukan. Ubah isi KANDIDAT sesuai lokasi dataset.")

KATEGORI = ["Kecil", "Sedang", "Besar"]


def angka(n):
    """Format angka gaya Indonesia: 1234567 -> 1.234.567"""
    return f"{n:,}".replace(",", ".")


# 1. Baca ukuran setiap citra (hanya header, cepat)
data = []
for p in sorted(DATASET.glob("*/*/*.jpeg")):
    with Image.open(p) as img:
        w, h = img.size
        mode = img.mode
    data.append({
        "file": str(p.relative_to(DATASET)).replace("\\", "/"),
        "kelas": p.parent.name,
        "lebar": w, "tinggi": h, "piksel": w * h,
        "mode": mode,
        "ukuran_kb": round(p.stat().st_size / 1024, 2),
    })

# 2. Urutkan berdasarkan jumlah piksel, lalu bagi tiga sama banyak (tertil)
data.sort(key=lambda d: (d["piksel"], d["file"]))
n = len(data)
batas = [0, n // 3, 2 * n // 3, n]
for i, k in enumerate(KATEGORI):
    for d in data[batas[i]:batas[i + 1]]:
        d["kategori"] = k

# 3. Tabel distribusi
print(f"Jumlah citra: {angka(n)}\n")
print(f"{'Kategori':8s} | {'Jumlah piksel':27s} | {'Contoh resolusi (min - maks)':31s} | "
      f"{'NORMAL':>6s} {'PNEU':>5s} {'RGB':>4s} {'Jml':>5s} | Ukuran file (KB)")
for k in KATEGORI:
    g = [d for d in data if d["kategori"] == k]
    pmin, pmaks = g[0], g[-1]
    nn = sum(d["kelas"] == "NORMAL" for d in g)
    rgb = sum(d["mode"] == "RGB" for d in g)
    kb = [d["ukuran_kb"] for d in g]
    print(f"{k:8s} | {angka(pmin['piksel']):>11s} - {angka(pmaks['piksel']):>13s} | "
          f"{pmin['lebar']} x {pmin['tinggi']} - {pmaks['lebar']} x {pmaks['tinggi']:<12} | "
          f"{nn:6d} {len(g) - nn:5d} {rgb:4d} {len(g):5d} | {min(kb):.2f} - {max(kb):.2f}")

# Cek apakah ada nilai piksel yang sama persis di perbatasan kategori
for i in (1, 2):
    a, b = data[batas[i] - 1], data[batas[i]]
    if a["piksel"] == b["piksel"]:
        print(f"\nCatatan: batas {KATEGORI[i - 1]}/{KATEGORI[i]} jatuh di jumlah piksel yang sama "
              f"({angka(a['piksel'])}).")

# 4. Simpan daftar lengkap untuk tahap pengambilan sampel
with open("dataset_kategori.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
    w.writeheader()
    w.writerows(data)
print("\nTersimpan: dataset_kategori.csv")

# 5. Gambar distribusi jumlah piksel dengan batas tertil
plt.rcParams["font.family"] = "serif"
mp = [d["piksel"] / 1e6 for d in data]
b1, b2 = data[batas[1]]["piksel"] / 1e6, data[batas[2]]["piksel"] / 1e6
fig, ax = plt.subplots(figsize=(9, 4))
ax.hist(mp, bins=60, color="#5B7DB1", edgecolor="white")
ax.axvspan(min(mp), b1, color="#D4EDDA", alpha=0.6, zorder=0)
ax.axvspan(b1, b2, color="#FFF3CD", alpha=0.6, zorder=0)
ax.axvspan(b2, max(mp), color="#F8D7DA", alpha=0.6, zorder=0)
for x in (b1, b2):
    ax.axvline(x, color="#33415C", linestyle="--", linewidth=1.2)
puncak = ax.get_ylim()[1]
ax.text((min(mp) + b1) / 2, puncak * 0.92, "Kecil", ha="center", fontsize=11, fontweight="bold")
ax.text((b1 + b2) / 2, puncak * 0.92, "Sedang", ha="center", fontsize=11, fontweight="bold")
ax.text((b2 + max(mp)) / 2, puncak * 0.92, "Besar", ha="center", fontsize=11, fontweight="bold")
ax.set_xlabel("Jumlah piksel (juta piksel)")
ax.set_ylabel("Jumlah citra")
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.savefig("Gambar_3.6_Distribusi_Resolusi.png", dpi=300)
print("Tersimpan: Gambar_3.6_Distribusi_Resolusi.png")