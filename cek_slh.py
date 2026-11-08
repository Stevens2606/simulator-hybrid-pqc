"""Cek cepat: tanda tangan lalu verifikasi satu citra dengan ketiga kombinasi, beberapa kali.

Tujuan: memastikan modul inti (core) memberi hasil VALID untuk citra tanpa manipulasi,
di luar simulator web.

Cara pakai (di WSL, venv-wsl aktif, dari folder simulator_hybrid):
    python cek_slh.py path/ke/citra.jpeg
Contoh:
    python cek_slh.py sampel/Besar/NORMAL2-IM-0137-0001.jpeg
"""

import sys

from core import citra, hybrid, proses
from core.kombinasi import KOMBINASI

if len(sys.argv) < 2:
    sys.exit("Sebutkan path citra, contoh: python cek_slh.py sampel/Besar/nama.jpeg")

img = citra.buka_citra(sys.argv[1])
print(f"Citra: {sys.argv[1]}  {img.size[0]}x{img.size[1]}  mode {img.mode}\n")

for kombinasi in KOMBINASI:
    kunci = hybrid.bangkitkan_kunci(kombinasi)
    kunci_publik = {kombinasi: hybrid.kunci_publik_dari(kunci)}
    for i in range(1, 6):
        png, _ = proses.tandatangani_citra(img, kunci)
        # verifikasi 2 kali dari byte yang sama, seperti simulator (saat sign lalu saat verifikasi)
        h1 = proses.verifikasi_citra(citra.buka_citra(png), kunci_publik)
        h2 = proses.verifikasi_citra(citra.buka_citra(png), kunci_publik)
        st = lambda h: h.get("status", "VALID" if h.get("valid") else "TIDAK VALID")
        print(f"{kombinasi:32s} ulangan {i}: verifikasi-1 {st(h1):11s} verifikasi-2 {st(h2):11s} "
              f"(ECDSA {h2.get('ecdsa_cocok')}, PQC {h2.get('pqc_cocok')})")
    print()