"""Membuat gambar contoh lima jenis manipulasi citra (subbab 3.8.2).

Memakai fungsi manipulasi yang SAMA dengan pengujian (core/manipulasi.py),
pada satu citra sampel kategori Besar.

Baris atas  : citra asli dan hasil kelima manipulasi.
Baris bawah : peta perbedaan |asli - hasil|, diperkuat agar perubahan kecil terlihat.

Cara pakai (di WSL, venv-wsl aktif, dari folder simulator_hybrid):
    python buat_gambar_manipulasi.py
Hasil: Gambar_Manipulasi_Citra.png
"""

import csv
import io
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from core import citra, manipulasi

# Ambil citra sampel pertama kategori Besar dari sampel_90.csv
with open("sampel_90.csv", encoding="utf-8") as f:
    baris = next(d for d in csv.DictReader(f) if d["kategori"] == "Besar")
path = Path("sampel") / "Besar" / Path(baris["file"]).name
asli = citra.buka_citra(str(path)).convert("L")
paket = "{}"  # paket tidak berpengaruh pada tampilan piksel
print("Citra contoh:", path, asli.size)

judul = ["Citra asli", "Perubahan satu piksel", "Penambahan bercak", "Kecerahan dan kontras",
         "Pemotongan tepi", "Kompresi ulang JPEG"]
hasil = [asli]
for fungsi in manipulasi.MANIPULASI_CITRA.values():
    hasil.append(Image.open(io.BytesIO(fungsi(asli, paket))).convert("L"))

a0 = np.array(asli, dtype=np.int16)
plt.rcParams["font.family"] = "serif"
fig, ax = plt.subplots(2, 6, figsize=(16, 6.2))
for i, (img, t) in enumerate(zip(hasil, judul)):
    ax[0, i].imshow(img, cmap="gray", vmin=0, vmax=255)
    ax[0, i].set_title(f"({chr(97 + i)}) {t}", fontsize=10)
    ax[0, i].axis("off")
    a1 = np.array(img, dtype=np.int16)
    if i == 0:
        ax[1, i].text(0.5, 0.5, "Baris bawah:\npeta perbedaan\n|asli − hasil|\n(makin terang =\nmakin berubah)",
                      ha="center", va="center", fontsize=10)
    elif a1.shape != a0.shape:
        ax[1, i].text(0.5, 0.5, f"Ukuran berubah\n{asli.width} × {asli.height}\n→ "
                      f"{img.width} × {img.height}", ha="center", va="center", fontsize=10)
    else:
        beda = np.abs(a1 - a0)
        n = int((beda > 0).sum())
        ax[1, i].imshow(beda / max(beda.max(), 1), cmap="hot", vmin=0, vmax=1)
        if n <= 4:  # satu piksel terlalu kecil untuk terlihat: tandai dengan lingkaran
            ys, xs = np.nonzero(beda)
            ax[1, i].scatter(xs, ys, s=300, facecolors="none", edgecolors="#00BFFF", linewidths=2)
        ax[1, i].set_title(f"{n:,} piksel berubah".replace(",", "."), fontsize=9)
    ax[1, i].axis("off")
plt.tight_layout()
plt.savefig("Gambar_Manipulasi_Citra.png", dpi=300)
print("Tersimpan: Gambar_Manipulasi_Citra.png")