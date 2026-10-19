"""Pengujian fungsional (subbab 3.8.1 - 3.8.3) pada 90 citra sampel.

Untuk setiap kombinasi hybrid dan setiap citra di sampel_90.csv:
  1. Skenario normal            : citra ditandatangani lalu diverifikasi  -> harapan VALID
                                  + cek hash citra PNG bertanda tangan == hash citra asli
  2. Manipulasi citra (5 jenis) : piksel diubah lalu diverifikasi          -> harapan TIDAK VALID
  3. Manipulasi tanda tangan    : paket diubah lalu diverifikasi           -> harapan TIDAK VALID
     (5 jenis, 6 kasus)

Cara pakai (di WSL, venv-wsl aktif, dari folder simulator_hybrid):
    python uji_fungsional.py              # 90 citra (lengkap)
    python uji_fungsional.py 3            # uji coba cepat: 3 citra pertama saja

Hasil:
  - ringkasan di terminal
  - hasil_uji_fungsional.csv (rincian setiap kasus)
"""

import csv
import sys
import time
from collections import defaultdict
from pathlib import Path

from core import citra, hybrid, manipulasi, proses
from core.kombinasi import KOMBINASI


def status_dari(hasil):
    """Mengambil status VALID / TIDAK VALID dari hasil verifikasi_citra."""
    if "status" in hasil:
        return hasil["status"]
    return "VALID" if hasil.get("valid") else "TIDAK VALID"


def baca_sampel(batas=None):
    with open("sampel_90.csv", encoding="utf-8") as f:
        data = list(csv.DictReader(f))
    if batas:
        data = data[:batas]
    for d in data:
        d["path"] = Path("sampel") / d["kategori"] / Path(d["file"]).name
        if not d["path"].exists():
            sys.exit(f"File sampel tidak ditemukan: {d['path']}. Jalankan dulu ambil_sampel.py")
    return data


def jalankan(batas=None):
    sampel = baca_sampel(batas)
    if len(sampel) < 2:
        sys.exit("Butuh minimal 2 citra (untuk uji penukaran paket).")

    baris = []
    ringkasan = defaultdict(lambda: [0, 0])   # (kombinasi, skenario) -> [sesuai, total]
    per_jenis = defaultdict(lambda: [0, 0])   # (kombinasi, jenis)    -> [sesuai, total]
    hash_sama = defaultdict(lambda: [0, 0])   # kombinasi -> [sama, total]
    mulai = time.time()

    for kombinasi in KOMBINASI:
        print(f"Menguji {kombinasi} ...", flush=True)
        kunci = hybrid.bangkitkan_kunci(kombinasi)
        kunci_publik = {kombinasi: hybrid.kunci_publik_dari(kunci)}

        # 1) tandatangani semua citra dulu (paket citra lain dibutuhkan untuk uji penukaran)
        bertanda = []
        for d in sampel:
            img_asli = citra.buka_citra(str(d["path"]))
            png, _ = proses.tandatangani_citra(img_asli, kunci)
            img_ttd = citra.buka_citra(png)           # dibaca ulang dari byte (seolah diunduh)
            sama = citra.hitung_hash(img_asli) == citra.hitung_hash(img_ttd)
            hash_sama[kombinasi][0] += sama
            hash_sama[kombinasi][1] += 1
            bertanda.append((d, img_ttd, citra.baca_paket(img_ttd), sama))

        # 2) jalankan semua kasus untuk setiap citra
        for i, (d, img_ttd, paket, sama) in enumerate(bertanda):
            paket_lain = bertanda[(i + 1) % len(bertanda)][2]
            kasus = [("Normal", "Tanpa perubahan", citra.simpan_png(img_ttd, paket), "VALID")]
            for jenis, fungsi in manipulasi.MANIPULASI_CITRA.items():
                kasus.append(("Manipulasi citra", jenis, fungsi(img_ttd, paket), "TIDAK VALID"))
            for jenis, fungsi in manipulasi.MANIPULASI_TANDA_TANGAN.items():
                kasus.append(("Manipulasi tanda tangan", jenis,
                              fungsi(img_ttd, paket, paket_citra_lain=paket_lain), "TIDAK VALID"))

            for skenario, jenis, data_file, harapan in kasus:
                hasil = proses.verifikasi_citra(citra.buka_citra(data_file), kunci_publik)
                status = status_dari(hasil)
                sesuai = status == harapan
                for kumpulan, kunci_ring in ((ringkasan, (kombinasi, skenario)),
                                             (per_jenis, (kombinasi, jenis))):
                    kumpulan[kunci_ring][0] += sesuai
                    kumpulan[kunci_ring][1] += 1
                baris.append({
                    "kombinasi": kombinasi, "citra": Path(d["file"]).name, "kategori": d["kategori"],
                    "kelas": d["kelas"], "skenario": skenario, "jenis": jenis,
                    "hash_tetap_sama": sama if skenario == "Normal" else "",
                    "harapan": harapan, "hasil": status, "sesuai": "Ya" if sesuai else "TIDAK",
                    "ecdsa_cocok": hasil.get("ecdsa_cocok", hasil.get("ecdsa", "")),
                    "pqc_cocok": hasil.get("pqc_cocok", hasil.get("pqc", "")),
                    "alasan": hasil.get("alasan", ""),
                })

    with open("hasil_uji_fungsional.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(baris[0].keys()))
        w.writeheader()
        w.writerows(baris)

    print(f"\nJumlah citra: {len(sampel)} | waktu total: {time.time() - mulai:.1f} detik")
    print("Rincian setiap kasus: hasil_uji_fungsional.csv\n")

    print("=== Hash citra bertanda tangan sama dengan hash citra asli ===")
    for k, (ok, total) in hash_sama.items():
        print(f"  {k:32} {ok}/{total}")

    print("\n=== Ringkasan per skenario (sesuai harapan) ===")
    for (k, s), (ok, total) in ringkasan.items():
        print(f"  {k:32} {s:26} {ok:>5}/{total:<5} ({100 * ok / total:5.1f}%)")

    print("\n=== Rincian per jenis manipulasi ===")
    for (k, j), (ok, total) in per_jenis.items():
        print(f"  {k:32} {j:46} {ok:>3}/{total:<3}")

    gagal = [b for b in baris if b["sesuai"] != "Ya"] + \
        [1 for ok, total in hash_sama.values() if ok != total]
    print("\nSEMUA KASUS SESUAI HARAPAN" if not gagal
          else f"\nADA {len(gagal)} KASUS TIDAK SESUAI, cek hasil_uji_fungsional.csv")


if __name__ == "__main__":
    jalankan(int(sys.argv[1]) if len(sys.argv) > 1 else None)