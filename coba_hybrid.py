from pathlib import Path
from core import citra, hybrid
from core.kombinasi import KOMBINASI

# Ambil citra pertama (hanya .jpeg, supaya .DS_Store tidak ikut)
path = next(Path("contoh_citra").glob("*.jpeg"))
img = citra.buka_citra(path)
hash_asli = citra.hitung_hash(img)

# Buat versi citra yang diubah 1 piksel (pojok kiri atas, nilainya ditambah 10)
img_ubah = img.copy()
nilai = img_ubah.getpixel((0, 0))
img_ubah.putpixel((0, 0), (nilai + 10) % 256)
hash_ubah = citra.hitung_hash(img_ubah)

print("Citra:", path.name, "\n")

for kode in KOMBINASI:
    kunci = hybrid.bangkitkan_kunci(kode)
    publik = hybrid.kunci_publik_dari(kunci)
    sig_ecdsa, sig_pqc = hybrid.tandatangani(hash_asli, kunci)

    print(kode)
    print("  Ukuran sig ECDSA :", len(sig_ecdsa), "byte")
    print("  Ukuran sig PQC   :", len(sig_pqc), "byte")
    print("  Citra asli       :", hybrid.verifikasi(hash_asli, sig_ecdsa, sig_pqc, publik))
    print("  Citra diubah 1px :", hybrid.verifikasi(hash_ubah, sig_ecdsa, sig_pqc, publik))
    print()