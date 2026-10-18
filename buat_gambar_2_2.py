"""Membuat Gambar 2.2: ilustrasi piksel pada citra rontgen dada."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle
from PIL import Image

N = 8  # ukuran area yang diperbesar: 8 x 8 piksel

path = next(Path("contoh_citra").glob("*.jpeg"))
img = np.array(Image.open(path).convert("L"))
tinggi, lebar = img.shape

# Cari area 8x8 di bagian tengah citra yang nilai pikselnya paling bervariasi
# (supaya angkanya tidak semuanya sama)
terbaik, posisi = -1, (0, 0)
for y in range(int(tinggi * 0.25), int(tinggi * 0.75), N):
    for x in range(int(lebar * 0.2), int(lebar * 0.8), N):
        variasi = img[y:y + N, x:x + N].std()
        if variasi > terbaik:
            terbaik, posisi = variasi, (y, x)
y0, x0 = posisi
area = img[y0:y0 + N, x0:x0 + N]

fig, (kiri, kanan) = plt.subplots(1, 2, figsize=(11, 5.2), dpi=200,
                                  gridspec_kw={"width_ratios": [1, 1.1]})

# (a) Citra utuh dengan kotak merah penanda area
kiri.imshow(img, cmap="gray", vmin=0, vmax=255)
besar = max(lebar, tinggi) * 0.04  # kotak dibuat sedikit lebih besar agar terlihat
kiri.add_patch(Rectangle((x0 - besar / 2, y0 - besar / 2), besar, besar,
                         fill=False, ec="red", lw=2))
kiri.set_title("(a) Citra rontgen dada", fontsize=12)
kiri.axis("off")

# (b) Area 8x8 diperbesar, setiap kotak berisi nilai pikselnya
kanan.imshow(area, cmap="gray", vmin=0, vmax=255)
for i in range(N):
    for j in range(N):
        nilai = int(area[i, j])
        kanan.text(j, i, str(nilai), ha="center", va="center", fontsize=10,
                   color="black" if nilai > 127 else "white")
kanan.set_xticks(np.arange(-0.5, N, 1), minor=True)
kanan.set_yticks(np.arange(-0.5, N, 1), minor=True)
kanan.grid(which="minor", color="red", lw=0.8)
kanan.tick_params(which="both", length=0, labelbottom=False, labelleft=False)
kanan.set_title(f"(b) Area {N}×{N} piksel diperbesar (nilai 0–255)", fontsize=12)

plt.tight_layout()
plt.savefig("Gambar_2.2_Ilustrasi_Piksel.png", bbox_inches="tight", facecolor="white")
print("Selesai: Gambar_2.2_Ilustrasi_Piksel.png")
print(f"Citra: {path.name}, area di x={x0}, y={y0}")