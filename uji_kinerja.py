"""Pengujian kinerja pada citra sampel (rancangan pengujian kinerja di Bab III).

Untuk setiap kombinasi, setiap citra, dan setiap pengulangan:
  1. bangkitkan pasangan kunci ECDSA + pasca-kuantum
  2. tandatangani citra : hash -> ECDSA -> PQC -> paket JSON -> disisipkan ke JPEG
  3. buka JPEG bertanda tangan, lalu verifikasi : baca paket + hash ulang -> ECDSA -> PQC -> aturan AND
Waktu ECDSA dan waktu pasca-kuantum dicatat TERPISAH, sehingga pembahasan bisa
membandingkan algoritma tunggal dengan skema hybrid tanpa pengujian tambahan.

Prosedur:
  - Sebelum mengukur satu kombinasi, dilakukan 1 putaran pemanasan (warm-up) yang dibuang.
  - Urutan kombinasi dan urutan citra diacak dengan seed tetap (SEED = 42), jadi selalu sama.
  - Setiap pengukuran langsung ditulis ke berkas. Kalau terhenti, jalankan perintah yang
    sama lagi: pengukuran yang sudah ada dilewati, sisanya dilanjutkan.

Cara pakai (WSL, venv-wsl aktif, dari folder proyek; tutup aplikasi lain, charger terpasang):
    python uji_kinerja.py           # lengkap: 90 citra x 10 pengulangan   -> folder hasil/
    python uji_kinerja.py 3 2       # uji coba: 3 citra x 2 pengulangan    -> folder hasil_uji_coba/
    python uji_kinerja.py olah      # hanya mengolah ulang data mentah di folder hasil/

Berkas yang dihasilkan (di folder hasil/):
  mentah/<kode>.csv            data mentah per kombinasi, 1 baris = 1 pengukuran (ditulis bertahap)
  pengaturan.json              jumlah citra, pengulangan, seed, dan daftar kombinasi
  data_mentah.xlsx / .csv      gabungan seluruh data mentah (+ sheet info_lingkungan)
  hasil_olahan.xlsx            sheet per_citra : 10 pengulangan diringkas jadi 1 nilai per citra
                               sheet ringkasan : per kombinasi x kategori -> n, rata-rata, SD, median, Q1, Q3, IQR
                               sheet status    : jumlah VALID / TIDAK VALID per kombinasi
  hasil_olahan_per_citra.csv, hasil_olahan_ringkasan.csv   isi yang sama dalam CSV

Asumsi versi: Python 3.14, liboqs 0.16.0 + liboqs-python 0.16.0.1, cryptography, Pillow,
psutil, openpyxl (untuk .xlsx; tanpa openpyxl hanya CSV yang dibuat).
"""

import csv
import json
import os
import platform
import random
import re
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime
from importlib import metadata
from pathlib import Path

from cryptography.hazmat.primitives import serialization

from core import citra, hybrid, proses
from core.kombinasi import KOMBINASI

SEED = 42
ULANG_DEFAULT = 10
N_CITRA_PENUH = 90
FILE_SAMPEL = "sampel_90.csv"
FOLDER_SAMPEL = Path("sampel")

# Cara meringkas 10 pengulangan menjadi 1 nilai per citra: "rata_rata" atau "median"
RINGKAS_PER_CITRA = "rata_rata"

# ---------------------------------------------------------------- kolom data mentah
KOLOM_ID = ["kode", "label", "algoritma", "level_nist", "kurva_ecdsa", "pqc",
            "citra", "kategori", "piksel", "mode", "ulangan",
            "status_verifikasi", "ecdsa_cocok", "pqc_cocok"]

METRIK_WAKTU = [
    # pembangkitan kunci
    "waktu_keygen_ecdsa_ms", "waktu_keygen_pqc_ms", "waktu_keygen_total_ms",
    # penandatanganan
    "waktu_hash_ms", "waktu_ttd_ecdsa_ms", "waktu_ttd_pqc_ms",
    "waktu_tanda_tangan_ms", "waktu_simpan_ms", "waktu_penandatanganan_total_ms",
    # verifikasi
    "waktu_baca_hash_ms", "waktu_verifikasi_ecdsa_ms", "waktu_verifikasi_pqc_ms",
    "waktu_cek_ttd_ms", "waktu_verifikasi_total_ms",
]
METRIK_UKURAN = [
    "sig_ecdsa_byte", "sig_pqc_byte", "paket_byte",
    "file_asli_byte", "file_bertanda_byte", "pertambahan_file_byte",
    "kunci_ecdsa_publik_byte", "kunci_ecdsa_privat_byte",
    "kunci_pqc_publik_byte", "kunci_pqc_privat_byte",
]
METRIK = METRIK_WAKTU + METRIK_UKURAN
KOLOM = KOLOM_ID + METRIK


# ---------------------------------------------------------------- bantuan umum
def nama_file(kode):
    """Kode kombinasi -> nama file yang aman (mis. 'ECDSA-P256+ML-DSA-44' -> 'ECDSA-P256_ML-DSA-44')."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", kode)


def bulat(x, digit=6):
    return "" if x is None else round(x, digit)


def ukuran_kunci(kunci):
    pub = kunci["ecdsa_publik"].public_bytes(serialization.Encoding.X962,
                                             serialization.PublicFormat.UncompressedPoint)
    return {
        "kunci_ecdsa_publik_byte": len(pub),
        "kunci_ecdsa_privat_byte": (kunci["ecdsa_privat"].curve.key_size + 7) // 8,
        "kunci_pqc_publik_byte": len(kunci["pqc_publik"]),
        "kunci_pqc_privat_byte": len(kunci["pqc_privat"]),
    }


def baca_sampel():
    if not Path(FILE_SAMPEL).exists():
        sys.exit(f"File {FILE_SAMPEL} tidak ditemukan. Jalankan dari folder proyek.")
    with open(FILE_SAMPEL, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def pilih_sampel(data, batas):
    """Untuk uji coba: ambil `batas` citra secara bergiliran dari tiap kategori."""
    if not batas or batas >= len(data):
        return data
    per_kat = defaultdict(list)
    for d in data:
        per_kat[d["kategori"]].append(d)
    hasil, i = [], 0
    while len(hasil) < batas:
        for daftar in per_kat.values():
            if i < len(daftar) and len(hasil) < batas:
                hasil.append(daftar[i])
        i += 1
    return hasil


def path_citra(d):
    return FOLDER_SAMPEL / d["kategori"] / Path(d["file"]).name


def urutan_kategori():
    """Urutan kategori mengikuti kemunculan di sampel_90.csv (untuk merapikan tabel olahan)."""
    try:
        urut = []
        for d in baca_sampel():
            if d["kategori"] not in urut:
                urut.append(d["kategori"])
        return urut
    except SystemExit:
        return []


# ---------------------------------------------------------------- pengaturan & lanjutan
def cek_pengaturan(folder, ulang, n_citra):
    """Pastikan data lama di folder ini dibuat dengan pengaturan yang sama."""
    file = folder / "pengaturan.json"
    sekarang = {
        "ulang": ulang, "n_citra": n_citra, "seed": SEED,
        "kombinasi": {k: {"pqc": v["pqc"], "ecdsa": hybrid.nama_kurva(k)} for k, v in KOMBINASI.items()},
    }
    if file.exists():
        lama = json.loads(file.read_text(encoding="utf-8"))
        for kunci in ("ulang", "n_citra", "seed"):
            if lama.get(kunci) != sekarang[kunci]:
                sys.exit(f"Folder {folder}/ berisi data dengan {kunci}={lama.get(kunci)}, "
                         f"sedangkan sekarang {kunci}={sekarang[kunci]}.\n"
                         f"Pindahkan atau hapus folder {folder}/ dulu, lalu jalankan lagi.")
        for kode, isi in lama.get("kombinasi", {}).items():
            if kode in sekarang["kombinasi"] and sekarang["kombinasi"][kode] != isi:
                sys.exit(f"Kombinasi {kode} di kombinasi.py berubah sejak data lama dibuat "
                         f"({isi} -> {sekarang['kombinasi'][kode]}).\n"
                         f"Data lama tidak bisa dicampur. Pindahkan folder {folder}/ dulu.")
        # kombinasi baru (crypto-agility) boleh ditambahkan; yang lama tetap dicatat
        sekarang["kombinasi"] = {**lama.get("kombinasi", {}), **sekarang["kombinasi"]}
    file.write_text(json.dumps(sekarang, indent=2), encoding="utf-8")


def baca_mentah(path):
    """Baca data mentah satu kombinasi. Baris yang rusak (mis. terpotong saat listrik mati) dibuang."""
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        if r.fieldnames != KOLOM:
            sys.exit(f"Kolom pada {path} berbeda dengan format sekarang. "
                     f"Pindahkan file itu (data format lama), lalu jalankan lagi.")
        return [b for b in r
                if None not in b.values() and b["status_verifikasi"] in ("VALID", "TIDAK VALID")]


# ---------------------------------------------------------------- satu pengukuran
def satu_pengukuran(img, kode):
    kunci, wk = proses.ukur_keygen_rinci(kode)
    jpeg_ttd, info = proses.tandatangani_citra(img, kunci)
    img_bertanda = citra.buka_citra(jpeg_ttd)                # seperti penerima membuka file JPEG
    hasil = proses.verifikasi_citra(img_bertanda, {kode: hybrid.kunci_publik_dari(kunci)})
    return kunci, wk, info, hasil


def susun_baris(kode, d, r, kunci, wk, info, hasil):
    k = KOMBINASI[kode]
    return {
        "kode": kode, "label": k.get("label", kode), "algoritma": k.get("algoritma", ""),
        "level_nist": k.get("level_nist", ""), "kurva_ecdsa": hybrid.nama_kurva(kode),
        "pqc": k["pqc"],
        "citra": Path(d["file"]).name, "kategori": d["kategori"],
        "piksel": d.get("piksel", ""), "mode": d.get("mode", ""), "ulangan": r,
        "status_verifikasi": hasil["status"],
        "ecdsa_cocok": hasil["ecdsa_cocok"], "pqc_cocok": hasil["pqc_cocok"],

        "waktu_keygen_ecdsa_ms": bulat(wk["keygen_ecdsa_ms"]),
        "waktu_keygen_pqc_ms": bulat(wk["keygen_pqc_ms"]),
        "waktu_keygen_total_ms": bulat(wk["keygen_total_ms"]),

        "waktu_hash_ms": bulat(info["waktu_hash_ms"]),
        "waktu_ttd_ecdsa_ms": bulat(info["waktu_ttd_ecdsa_ms"]),
        "waktu_ttd_pqc_ms": bulat(info["waktu_ttd_pqc_ms"]),
        "waktu_tanda_tangan_ms": bulat(info["waktu_tanda_tangan_ms"]),
        "waktu_simpan_ms": bulat(info["waktu_simpan_ms"]),
        "waktu_penandatanganan_total_ms": bulat(info["waktu_total_ms"]),

        "waktu_baca_hash_ms": bulat(hasil["waktu_baca_hash_ms"]),
        "waktu_verifikasi_ecdsa_ms": bulat(hasil["waktu_verifikasi_ecdsa_ms"]),
        "waktu_verifikasi_pqc_ms": bulat(hasil["waktu_verifikasi_pqc_ms"]),
        "waktu_cek_ttd_ms": bulat(hasil["waktu_cek_ttd_ms"]),
        "waktu_verifikasi_total_ms": bulat(hasil["waktu_verifikasi_ms"]),

        "sig_ecdsa_byte": info["ukuran_sig_ecdsa"], "sig_pqc_byte": info["ukuran_sig_pqc"],
        "paket_byte": info["ukuran_paket"],
        "file_asli_byte": info["ukuran_file_asli"], "file_bertanda_byte": info["ukuran_file_bertanda"],
        "pertambahan_file_byte": info["pertambahan_file"],
        **ukuran_kunci(kunci),
    }


def cek_kondisi_laptop():
    try:
        import psutil
        baterai = psutil.sensors_battery()
        if baterai is not None and not baterai.power_plugged:
            print("PERINGATAN: charger tidak terpasang. Pasang charger agar kinerja CPU stabil.\n")
    except Exception:
        pass   # di WSL informasi baterai sering tidak tersedia
    print("Pastikan aplikasi lain sudah ditutup (end task) sebelum pengujian lengkap.\n")


# ---------------------------------------------------------------- pengujian
def jalankan(batas, ulang, folder):
    folder_mentah = folder / "mentah"
    folder_mentah.mkdir(parents=True, exist_ok=True)

    sampel = pilih_sampel(baca_sampel(), batas)
    for d in sampel:
        if not path_citra(d).exists():
            sys.exit(f"Citra tidak ditemukan: {path_citra(d)}")
    cek_pengaturan(folder, ulang, len(sampel))
    cek_kondisi_laptop()

    urutan = list(KOMBINASI)
    random.Random(SEED).shuffle(urutan)

    target = len(sampel) * ulang
    total = len(urutan) * target
    print(f"{len(sampel)} citra x {ulang} pengulangan x {len(urutan)} kombinasi = {total} pengukuran")
    print(f"Hasil disimpan di folder {folder}/\n")

    sudah_ada = {kode: baca_mentah(folder_mentah / f"{nama_file(kode)}.csv") for kode in urutan}
    sisa_total = sum(max(target - len(b), 0) for b in sudah_ada.values())
    if sisa_total < total:
        print(f"Melanjutkan: {total - sisa_total} pengukuran sudah ada, {sisa_total} tersisa.\n")

    mulai, dikerjakan, tidak_valid = time.time(), 0, 0
    for no, kode in enumerate(urutan, 1):
        path = folder_mentah / f"{nama_file(kode)}.csv"
        lama = sudah_ada[kode]
        selesai = {(b["citra"], int(b["ulangan"])) for b in lama}
        if len(selesai) >= target:
            print(f"[{no}/{len(urutan)}] {kode}: sudah lengkap, dilewati")
            continue
        print(f"[{no}/{len(urutan)}] {kode}: {target - len(selesai)} pengukuran", flush=True)

        # tulis ulang file dengan baris yang utuh saja, lalu lanjutkan menambah baris
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=KOLOM)
            w.writeheader()
            w.writerows(lama)

        urutan_citra = list(sampel)
        random.Random(f"{SEED}:{kode}").shuffle(urutan_citra)

        # pemanasan 1 kali, hasilnya dibuang
        satu_pengukuran(citra.buka_citra(str(path_citra(urutan_citra[0]))), kode)

        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=KOLOM)
            for d in urutan_citra:
                nama = Path(d["file"]).name
                belum = [r for r in range(1, ulang + 1) if (nama, r) not in selesai]
                if not belum:
                    continue
                img = citra.buka_citra(str(path_citra(d)))
                for r in belum:
                    kunci, wk, info, hasil = satu_pengukuran(img, kode)
                    baris = susun_baris(kode, d, r, kunci, wk, info, hasil)
                    w.writerow(baris)
                    f.flush()
                    os.fsync(f.fileno())          # agar tidak hilang kalau laptop mati

                    dikerjakan += 1
                    tidak_valid += baris["status_verifikasi"] != "VALID"
                    if dikerjakan % 50 == 0 or dikerjakan == sisa_total:
                        lalu = time.time() - mulai
                        perkiraan = lalu / dikerjakan * (sisa_total - dikerjakan)
                        print(f"    {dikerjakan}/{sisa_total} | berjalan {lalu / 60:.1f} menit | "
                              f"perkiraan sisa {perkiraan / 60:.1f} menit", flush=True)

    print(f"\nPengukuran selesai dalam {(time.time() - mulai) / 60:.1f} menit.")
    if tidak_valid:
        print(f"PERINGATAN: {tidak_valid} verifikasi tidak VALID. Cek kolom status_verifikasi.")
    olah(folder)


# ---------------------------------------------------------------- pengolahan
def ke_angka(b):
    """Ubah teks dari CSV menjadi angka untuk kolom metrik."""
    hasil = dict(b)
    for m in METRIK:
        hasil[m] = float(b[m]) if b[m] not in ("", None) else None
    hasil["ulangan"] = int(b["ulangan"])
    try:
        hasil["level_nist"] = int(b["level_nist"])
    except (TypeError, ValueError):
        pass
    return hasil


def statistik(nilai):
    n = len(nilai)
    if n == 0:
        return {"n": 0, "rata_rata": None, "sd": None, "median": None, "q1": None, "q3": None, "iqr": None}
    sd = statistics.stdev(nilai) if n > 1 else 0.0          # SD sampel (pembagi n-1)
    if n > 1:
        q1, _, q3 = statistics.quantiles(nilai, n=4, method="inclusive")
    else:
        q1 = q3 = nilai[0]
    return {"n": n, "rata_rata": statistics.fmean(nilai), "sd": sd,
            "median": statistics.median(nilai), "q1": q1, "q3": q3, "iqr": q3 - q1}


def ringkas(nilai):
    if not nilai:
        return None
    return statistics.median(nilai) if RINGKAS_PER_CITRA == "median" else statistics.fmean(nilai)


def info_lingkungan(folder):
    def versi(paket):
        try:
            return metadata.version(paket)
        except metadata.PackageNotFoundError:
            return "-"
    baris = [("tanggal_olah", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
             ("python", platform.python_version()),
             ("sistem", platform.platform()),
             ("prosesor", platform.processor() or "-"),
             ("jumlah_cpu_logis", os.cpu_count())]
    try:
        import oqs
        baris.append(("liboqs", oqs.oqs_version()))
        baris.append(("liboqs-python", oqs.oqs_python_version()))
    except Exception:
        baris.append(("liboqs", "-"))
    for p in ("cryptography", "pillow", "psutil", "openpyxl"):
        baris.append((p, versi(p)))
    try:
        import psutil
        baris.append(("ram_total_gb", round(psutil.virtual_memory().total / 1024 ** 3, 2)))
    except Exception:
        pass
    file = folder / "pengaturan.json"
    if file.exists():
        p = json.loads(file.read_text(encoding="utf-8"))
        baris += [("seed", p.get("seed")), ("pengulangan_per_citra", p.get("ulang")),
                  ("jumlah_citra", p.get("n_citra"))]
    baris.append(("ringkasan_per_citra", RINGKAS_PER_CITRA))
    return [{"butir": a, "nilai": b} for a, b in baris]


def tulis_csv(path, kolom, baris):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=kolom, extrasaction="ignore")
        w.writeheader()
        w.writerows(baris)


def tulis_xlsx(path, sheets):
    """sheets: {nama_sheet: (kolom, daftar_baris_dict)}"""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError:
        print(f"openpyxl tidak terpasang, {path.name} tidak dibuat (CSV tetap ada). "
              f"Pasang dengan: pip install openpyxl")
        return
    wb = Workbook()
    wb.remove(wb.active)
    for nama, (kolom, baris) in sheets.items():
        ws = wb.create_sheet(nama)
        ws.append(kolom)
        for sel in ws[1]:
            sel.font = Font(bold=True)
        for b in baris:
            ws.append([b.get(k) for k in kolom])
        ws.freeze_panes = "A2"
    wb.save(path)


def olah(folder):
    folder_mentah = folder / "mentah"
    urut_kode = {k: i for i, k in enumerate(KOMBINASI)}
    urut_kat = {k: i for i, k in enumerate(urutan_kategori())}

    semua = []
    for kode in KOMBINASI:
        semua += [ke_angka(b) for b in baca_mentah(folder_mentah / f"{nama_file(kode)}.csv")]
    if not semua:
        print(f"Belum ada data mentah di {folder_mentah}/.")
        return

    kunci_urut = lambda b: (urut_kode.get(b["kode"], 999), urut_kat.get(b["kategori"], 999),
                            b["citra"], b.get("ulangan", 0))
    semua.sort(key=kunci_urut)

    # 1) data mentah gabungan
    lingkungan = info_lingkungan(folder)
    tulis_csv(folder / "data_mentah.csv", KOLOM, semua)
    tulis_xlsx(folder / "data_mentah.xlsx",
               {"data_mentah": (KOLOM, semua), "info_lingkungan": (["butir", "nilai"], lingkungan)})

    # 2) per citra: pengulangan diringkas menjadi satu nilai per citra
    grup = defaultdict(list)
    for b in semua:
        grup[(b["kode"], b["citra"])].append(b)
    kolom_id_citra = ["kode", "label", "algoritma", "level_nist", "kurva_ecdsa", "pqc",
                      "citra", "kategori", "piksel", "mode"]
    per_citra = []
    for daftar in grup.values():
        baris = {k: daftar[0][k] for k in kolom_id_citra}
        baris["n_ulangan"] = len(daftar)
        baris["n_tidak_valid"] = sum(b["status_verifikasi"] != "VALID" for b in daftar)
        for m in METRIK:
            baris[m] = ringkas([b[m] for b in daftar if b[m] is not None])
        per_citra.append(baris)
    per_citra.sort(key=kunci_urut)
    kolom_per_citra = kolom_id_citra + ["n_ulangan", "n_tidak_valid"] + METRIK

    # 3) ringkasan per kombinasi x kategori (dan "semua" kategori), N = jumlah citra
    kelompok = defaultdict(list)
    for b in per_citra:
        kelompok[(b["kode"], b["kategori"])].append(b)
        kelompok[(b["kode"], "semua")].append(b)
    ringkasan = []
    for (kode, kategori), daftar in kelompok.items():
        k0 = daftar[0]
        for m in METRIK:
            s = statistik([b[m] for b in daftar if b[m] is not None])
            ringkasan.append({"kode": kode, "label": k0["label"], "algoritma": k0["algoritma"],
                              "level_nist": k0["level_nist"], "kurva_ecdsa": k0["kurva_ecdsa"],
                              "kategori": kategori, "metrik": m, **s})
    urut_kat_semua = {**urut_kat, "semua": 998}
    urut_metrik = {m: i for i, m in enumerate(METRIK)}
    ringkasan.sort(key=lambda b: (urut_kode.get(b["kode"], 999), urut_kat_semua.get(b["kategori"], 999),
                                  urut_metrik[b["metrik"]]))
    kolom_ringkasan = ["kode", "label", "algoritma", "level_nist", "kurva_ecdsa", "kategori", "metrik",
                       "n", "rata_rata", "sd", "median", "q1", "q3", "iqr"]

    # 4) status verifikasi per kombinasi
    status = []
    for kode in KOMBINASI:
        baris_k = [b for b in semua if b["kode"] == kode]
        if baris_k:
            valid = sum(b["status_verifikasi"] == "VALID" for b in baris_k)
            status.append({"kode": kode, "label": baris_k[0]["label"], "jumlah_pengukuran": len(baris_k),
                           "valid": valid, "tidak_valid": len(baris_k) - valid})
    kolom_status = ["kode", "label", "jumlah_pengukuran", "valid", "tidak_valid"]

    tulis_csv(folder / "hasil_olahan_per_citra.csv", kolom_per_citra, per_citra)
    tulis_csv(folder / "hasil_olahan_ringkasan.csv", kolom_ringkasan, ringkasan)
    tulis_xlsx(folder / "hasil_olahan.xlsx", {
        "ringkasan": (kolom_ringkasan, ringkasan),
        "per_citra": (kolom_per_citra, per_citra),
        "status": (kolom_status, status),
        "info_lingkungan": (["butir", "nilai"], lingkungan),
    })

    belum = [k for k in KOMBINASI if not any(b["kode"] == k for b in status)]
    print(f"\nData diolah: {len(semua)} pengukuran dari {len(status)} kombinasi.")
    if belum:
        print(f"Kombinasi yang belum ada datanya: {', '.join(belum)}")
    print(f"Berkas: {folder}/data_mentah.xlsx dan {folder}/hasil_olahan.xlsx (beserta versi CSV)")


# ---------------------------------------------------------------- titik masuk
if __name__ == "__main__":
    argumen = [a for a in sys.argv[1:] if a != "lanjut"]   # "lanjut" tidak perlu lagi, otomatis

    if argumen and argumen[0] == "olah":
        olah(Path("hasil"))
        sys.exit(0)

    try:
        batas = int(argumen[0]) if argumen else None
        ulang = int(argumen[1]) if len(argumen) > 1 else ULANG_DEFAULT
    except ValueError:
        sys.exit("Pemakaian: python uji_kinerja.py [jumlah_citra] [pengulangan]  |  python uji_kinerja.py olah")

    penuh = batas in (None, N_CITRA_PENUH) and ulang == ULANG_DEFAULT
    try:
        jalankan(batas, ulang, Path("hasil") if penuh else Path("hasil_uji_coba"))
    except KeyboardInterrupt:
        print("\nDihentikan. Data yang sudah tercatat aman; jalankan perintah yang sama untuk melanjutkan.")