"""Membuat Gambar 2.1: contoh citra rontgen dada NORMAL dan PNEUMONIA (subbab 2.1.1).

Berbeda dengan Gambar 3.4 (4 citra untuk analisis dataset), gambar ini hanya
berisi 1 citra NORMAL dan 1 citra PNEUMONIA sebagai ilustrasi teori.
Citra yang sudah dipakai di Gambar 3.4 dan Gambar 2.2 tidak dipilih lagi.

Cara pakai (di WSL, venv-wsl aktif, dari folder simulator_hybrid):
    python buat_gambar_2_1.py
Hasil: Gambar_2.1_Normal_Pneumonia.png
"""

import random
from pathlib import Path

import matplotlib.pyplot as plt
from PIL import Image

KANDIDAT = [Path("/mnt/d/Perkuliahan/TA/dataset/chest_xray"),
            Path(r"D:\Perkuliahan\TA\dataset\chest_xray")]
DATASET = next((p for p in KANDIDAT if p.exists()), None)
if DATASET is None:
    raise SystemExit("Folder dataset tidak ditemukan. Ubah isi KANDIDAT sesuai lokasi dataset.")

# citra yang sudah dipakai di gambar lain, supaya tidak dobel
SUDAH_DIPAKAI = {"NORMAL2-IM-0702-0001.jpeg", "NORMAL2-IM-0401-0001.jpeg",
                 "person341_virus_699.jpeg", "person472_bacteria_2014.jpeg",
                 "person1355_virus_2336.jpeg"}

random.seed(21)  # angka tetap supaya citra yang terpilih selalu sama


def ambil(kelas):
    """Mengambil 1 citra acak grayscale dari folder train suatu kelas.
    Dipilih citra dengan perbandingan lebar:tinggi mendekati persegi (0,8 - 1,25)
    agar kedua panel tampil seimbang."""
    semua = sorted(p for p in DATASET.glob(f"train/{kelas}/*.jpeg")
                   if p.name not in SUDAH_DIPAKAI)
    random.shuffle(semua)
    for p in semua:
        with Image.open(p) as img:
            if img.mode == "L" and 0.8 <= img.width / img.height <= 1.25:
                return p
    raise SystemExit(f"Tidak ada citra grayscale di kelas {kelas}")


pilihan = [("(a) Normal", ambil("NORMAL")), ("(b) Pneumonia", ambil("PNEUMONIA"))]

fig, ax = plt.subplots(1, 2, figsize=(8, 4.4))
for a, (judul, path) in zip(ax, pilihan):
    img = Image.open(path)
    a.imshow(img, cmap="gray", vmin=0, vmax=255)
    a.set_aspect("equal")
    a.axis("off")
    a.set_title(judul, fontsize=12, fontfamily="serif", y=-0.1)
    print(f"{judul:14s} {path.relative_to(DATASET)}  {img.width}x{img.height}  mode {img.mode}")

plt.tight_layout()
plt.savefig("Gambar_2.1_Normal_Pneumonia.png", dpi=300, bbox_inches="tight")
print("Selesai: Gambar_2.1_Normal_Pneumonia.png")