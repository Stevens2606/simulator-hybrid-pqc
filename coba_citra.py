from pathlib import Path
from core import citra

# ambil citra pertama di folder contoh_citra
path = next(Path("contoh_citra").iterdir())
img = citra.buka_citra(path)
print("Citra      :", path.name, img.size, "mode", img.mode)

hash_asli = citra.hitung_hash(img)
print("Hash asli  :", hash_asli.hex())

# simpan PNG dengan paket contoh (tanda tangan palsu, hanya untuk uji)
paket = citra.buat_paket("ECDSA-P256+ML-DSA-44", b"contoh-ecdsa", b"contoh-pqc")
png = citra.simpan_png(img, paket)

# buka lagi PNG-nya
img2 = citra.buka_citra(png)
print("Hash PNG   :", citra.hitung_hash(img2).hex())
print("Hash sama? :", citra.hitung_hash(img2) == hash_asli)
print("Paket ada? :", citra.baca_paket(img2) is not None)
print("Isi paket  :", citra.urai_paket(citra.baca_paket(img2))[0])