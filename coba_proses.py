from pathlib import Path

from core import citra, hybrid, proses
from core.kombinasi import KOMBINASI

folder_keluaran = Path("keluaran")
folder_keluaran.mkdir(exist_ok=True)

path = next(Path("contoh_citra").glob("*.jpeg"))
img = citra.buka_citra(path)
print("Citra:", path.name, img.size, "\n")

kunci_publik = {}

for kode in KOMBINASI:
    # Bangkitkan kunci, simpan kunci publiknya
    kunci, ms_keygen = proses.ukur_keygen(kode)
    kunci_publik[kode] = hybrid.kunci_publik_dari(kunci)

    # Tanda tangan, lalu simpan PNG-nya ke folder keluaran
    png, info = proses.tandatangani_citra(img, kunci)
    file_png = folder_keluaran / f"{path.stem}_{kode}.png"
    file_png.write_bytes(png)

    print(kode)
    print(f"  Keygen           : {ms_keygen:.3f} ms")
    print(f"  Hash             : {info['waktu_hash_ms']:.3f} ms")
    print(f"  Tanda tangan     : {info['waktu_tanda_tangan_ms']:.3f} ms")
    print(f"  Pertambahan file : {info['pertambahan_file']} byte")
    print(f"  Disimpan ke      : {file_png}")

    # Kasus 1: citra bertanda tangan, tidak diubah
    h = proses.verifikasi_citra(citra.buka_citra(png), kunci_publik)
    print(f"  [1] Asli               : {h['status']} - {h['alasan']}")

    # Kasus 2: citra JPEG asli, belum ditandatangani
    h = proses.verifikasi_citra(img, kunci_publik)
    print(f"  [2] Tanpa tanda tangan : {h['status']} - {h['alasan']}")

    # Kasus 3: piksel diubah, paket asli disalin ke citra baru
    asli = citra.buka_citra(png)
    paket_asli = citra.baca_paket(asli)
    ubah = asli.copy()
    ubah.putpixel((0, 0), (ubah.getpixel((0, 0)) + 10) % 256)
    png_ubah = citra.simpan_png(ubah, paket_asli)
    h = proses.verifikasi_citra(citra.buka_citra(png_ubah), kunci_publik)
    print(f"  [3] Diubah + paket asli: {h['status']} - {h['alasan']}")
    print()