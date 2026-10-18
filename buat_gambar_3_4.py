"""Membuat Gambar 3.4: contoh citra rontgen dada NORMAL dan PNEUMONIA dari dataset.

Cara pakai (dari folder simulator_hybrid):
    python buat_gambar_3_4.py
Hasil: Gambar_3.4_Contoh_Citra_Dataset.png
"""

import random
from pathlib import Path

import matplotlib.pyplot as plt
from PIL import Image

# Lokasi dataset. Script mencoba path WSL dulu, lalu path Windows.
KANDIDAT = [Path("/mnt/d/Perkuliahan/TA/dataset/chest_xray"),
            Path(r"D:\Perkuliahan\TA\dataset\chest_xray")]
DATASET = next((p for p in KANDIDAT if p.exists()), None)
if DATASET is None:
    raise SystemExit("Folder dataset tidak ditemukan. Ubah isi KANDIDAT sesuai lokasi dataset.")

random.seed(17)  # angka tetap supaya citra yang terpilih selalu sama


def ambil(kelas, jumlah=2):
    """Mengambil beberapa citra acak dari satu kelas (gabungan train, test, val)."""
    semua = sorted(p for p in DATASET.glob(f"*/{kelas}/*.jpeg"))
    return random.sample(semua, jumlah)


normal = ambil("NORMAL")
pneumonia = ambil("PNEUMONIA")

fig, ax = plt.subplots(1, 4, figsize=(12, 3.6))
for i, path in enumerate(normal + pneumonia):
    img = Image.open(path)
    ax[i].imshow(img.convert("L"), cmap="gray")
    ax[i].set_title(f"{path.name}\n{img.width} × {img.height} piksel", fontsize=9,
                    fontfamily="serif")
    ax[i].axis("off")
    print(f"{'NORMAL' if i < 2 else 'PNEUMONIA':10s} {path.relative_to(DATASET)}  "
          f"{img.width}x{img.height}  {path.stat().st_size / 1024:.2f} KB")

fig.text(0.27, 0.03, "(a) NORMAL", ha="center", fontsize=12, fontfamily="serif")
fig.text(0.75, 0.03, "(b) PNEUMONIA", ha="center", fontsize=12, fontfamily="serif")
plt.tight_layout(rect=(0, 0.07, 1, 1))
plt.savefig("Gambar_3.4_Contoh_Citra_Dataset.png", dpi=300)
print("Selesai: Gambar_3.4_Contoh_Citra_Dataset.png")