"""Rekap hasil pengujian untuk Bab IV: tabel ringkasan dan grafik.

Membaca:
  - hasil_uji_fungsional.csv  (dari uji_fungsional.py)
  - hasil_uji_kinerja.csv     (dari uji_kinerja.py)

Menghasilkan folder hasil_rekap/ berisi:
  Tabel (CSV + XLSX dengan nama sama, angka memakai koma desimal agar mudah ditempel ke Word;
         buka versi .xlsx di Excel):
    tabel_fungsional_skenario.csv   sesuai harapan per kombinasi dan skenario
    tabel_fungsional_jenis.csv      sesuai harapan per jenis manipulasi
    tabel_waktu.csv                 rata-rata ± SD waktu per kombinasi dan kategori
    tabel_ukuran.csv                ukuran kunci, tanda tangan, paket, pertambahan file
    tabel_memori.csv                memori puncak per kombinasi dan kategori
  Grafik (PNG 300 dpi):
    grafik_1_waktu_tanda_tangan.png
    grafik_2_waktu_verifikasi.png
    grafik_3_komponen_penandatanganan.png
    grafik_4_waktu_keygen.png
    grafik_5_ukuran.png
    grafik_6_memori.png
    grafik_7_verifikasi_vs_piksel.png

Cara pakai (di WSL, venv-wsl aktif, dari folder simulator_hybrid):
    python rekap_hasil.py
"""

import csv
import statistics as st
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter

KELUAR = Path("hasil_rekap")
KOMBINASI = ["ECDSA-P256+ML-DSA-44", "ECDSA-P256+Falcon-512", "ECDSA-P256+SLH-DSA-SHA2-128f"]
LABEL = {"ECDSA-P256+ML-DSA-44": "ECDSA + ML-DSA-44",
         "ECDSA-P256+Falcon-512": "ECDSA + Falcon-512",
         "ECDSA-P256+SLH-DSA-SHA2-128f": "ECDSA + SLH-DSA-128f"}
WARNA = {"ECDSA-P256+ML-DSA-44": "#2a78d6",           # biru
         "ECDSA-P256+Falcon-512": "#eb6834",           # oranye
         "ECDSA-P256+SLH-DSA-SHA2-128f": "#1baf7a"}    # hijau toska
KATEGORI = ["Kecil", "Sedang", "Besar"]
TINTA, TINTA_2, GARIS = "#1d232b", "#5b6472", "#e3e6ea"

plt.rcParams.update({
    "font.family": "serif", "font.size": 10, "axes.edgecolor": GARIS, "axes.labelcolor": TINTA,
    "xtick.color": TINTA_2, "ytick.color": TINTA_2, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": GARIS, "grid.linewidth": 0.6,
    "axes.axisbelow": True, "legend.frameon": False, "savefig.dpi": 300, "savefig.bbox": "tight",
})


# ---------------------------------------------------------------- bantuan
def angka(x, des=3):
    """Format angka gaya Indonesia: 1234.5 -> 1.234,500"""
    s = f"{x:,.{des}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def format_sumbu(ax, sumbu="y"):
    """Angka pada sumbu memakai format Indonesia (koma desimal, titik ribuan)."""
    fmt = FuncFormatter(lambda v, _: angka(v, 0) if float(v).is_integer() else angka(v, 1))
    (ax.yaxis if sumbu == "y" else ax.xaxis).set_major_formatter(fmt)


def simpan(fig, nama):
    for ax in fig.axes:
        format_sumbu(ax, "y")
    fig.savefig(KELUAR / nama)
    plt.close(fig)


def baca(path):
    if not Path(path).exists():
        raise SystemExit(f"File {path} tidak ditemukan. Jalankan dulu script pengujiannya.")
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def tulis(nama, kolom, baris):
    """Simpan tabel sebagai CSV (untuk script) dan XLSX (untuk dibuka di Excel / disalin ke Word)."""
    with open(KELUAR / nama, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(kolom)
        w.writerows(baris)
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font
    except ImportError:
        print(f"  (openpyxl belum terpasang, {nama} hanya disimpan sebagai CSV)")
        return
    wb = Workbook()
    ws = wb.active
    ws.title = Path(nama).stem[:31]
    ws.append(kolom)
    for b in baris:
        ws.append([str(x) for x in b])
    for sel in ws[1]:
        sel.font = Font(bold=True)
    for kol in ws.columns:
        lebar = max(len(str(s.value or "")) for s in kol)
        ws.column_dimensions[kol[0].column_letter].width = min(lebar + 2, 60)
        for s in kol:
            s.alignment = Alignment(vertical="top")
    wb.save(KELUAR / Path(nama).with_suffix(".xlsx").name)


def ringkas(nilai):
    return (st.mean(nilai), st.stdev(nilai) if len(nilai) > 1 else 0.0, len(nilai))


def label_batang(ax, batang, teks, ukuran=8, sd=None):
    """Label nilai di atas batang; jika ada error bar, label diletakkan di atas ujung error bar."""
    sd = sd or [0] * len(teks)
    for b, t, e in zip(batang, teks, sd):
        ax.annotate(t, (b.get_x() + b.get_width() / 2, b.get_height() + e), xytext=(0, 3),
                    textcoords="offset points", ha="center", va="bottom", fontsize=ukuran, color=TINTA)


def batang_kelompok(ax, data, metrik, satuan, des=3, sd=True):
    """Batang berkelompok: sumbu x = kategori, warna = kombinasi."""
    x = np.arange(len(KATEGORI))
    lebar = 0.26
    for i, k in enumerate(KOMBINASI):
        rata = [data[(k, kat)][metrik][0] for kat in KATEGORI]
        simp = [data[(k, kat)][metrik][1] for kat in KATEGORI] if sd else None
        b = ax.bar(x + (i - 1) * lebar, rata, lebar * 0.92, color=WARNA[k], label=LABEL[k],
                   yerr=simp, error_kw={"elinewidth": 0.8, "capsize": 2, "ecolor": TINTA_2})
        label_batang(ax, b, [angka(v, des) for v in rata], 7, simp)
    ax.set_xticks(x, [f"Kategori {k}" for k in KATEGORI])
    ax.set_ylabel(satuan)
    ax.legend(loc="upper left", ncol=3, fontsize=8)
    ax.margins(y=0.18)


# ---------------------------------------------------------------- fungsional
def rekap_fungsional():
    data = baca("hasil_uji_fungsional.csv")
    per_skenario = defaultdict(lambda: [0, 0])
    per_jenis = defaultdict(lambda: [0, 0])
    alasan = {}
    hash_sama = defaultdict(lambda: [0, 0])
    for r in data:
        ok = r["sesuai"] == "Ya"
        for kum, kunci in ((per_skenario, (r["kombinasi"], r["skenario"])),
                           (per_jenis, (r["skenario"], r["jenis"], r["kombinasi"]))):
            kum[kunci][0] += ok
            kum[kunci][1] += 1
        alasan[(r["skenario"], r["jenis"])] = r["alasan"]
        if r["skenario"] == "Normal":
            hash_sama[r["kombinasi"]][0] += r["hash_tetap_sama"] in ("True", "true", "1")
            hash_sama[r["kombinasi"]][1] += 1

    skenario = ["Normal", "Manipulasi citra", "Manipulasi tanda tangan"]
    baris = []
    for s in skenario:
        b = [s]
        for k in KOMBINASI:
            ok, n = per_skenario[(k, s)]
            b.append(f"{ok}/{n} ({angka(100 * ok / n, 1)}%)" if n else "-")
        baris.append(b)
    baris.append(["Hash tetap sama (skenario normal)"] +
                 [f"{hash_sama[k][0]}/{hash_sama[k][1]}" for k in KOMBINASI])
    tulis("tabel_fungsional_skenario.csv", ["Skenario"] + [LABEL[k] for k in KOMBINASI], baris)

    jenis_urut = list(dict.fromkeys((r["skenario"], r["jenis"]) for r in data))
    baris = []
    for s, j in jenis_urut:
        b = [s, j]
        for k in KOMBINASI:
            ok, n = per_jenis[(s, j, k)]
            b.append(f"{ok}/{n}")
        b.append(alasan[(s, j)])
        baris.append(b)
    tulis("tabel_fungsional_jenis.csv",
          ["Skenario", "Jenis"] + [LABEL[k] for k in KOMBINASI] + ["Alasan yang ditampilkan"], baris)
    total_ok = sum(1 for r in data if r["sesuai"] == "Ya")
    print(f"Fungsional: {total_ok}/{len(data)} kasus sesuai harapan")


# ---------------------------------------------------------------- kinerja
METRIK_WAKTU = [("waktu_keygen_ms", "Waktu pembangkitan kunci"),
                ("waktu_ttd_saja_ms", "Waktu tanda tangan (ECDSA + PQC)"),
                ("waktu_hash_ms", "Waktu hash"),
                ("waktu_simpan_ms", "Waktu simpan PNG"),
                ("waktu_penandatanganan_ms", "Waktu penandatanganan total"),
                ("waktu_verifikasi_ms", "Waktu verifikasi")]
METRIK_MEMORI = [("memori_puncak_ttd_kb", "Memori puncak penandatanganan"),
                 ("memori_puncak_verifikasi_kb", "Memori puncak verifikasi")]


def rekap_kinerja():
    data = baca("hasil_uji_kinerja.csv")
    kolom = set(data[0].keys())
    semua_metrik = [m for m, _ in METRIK_WAKTU + METRIK_MEMORI if m in kolom]
    grup = defaultdict(lambda: defaultdict(list))
    for r in data:
        for kat in (r["kategori"], "Semua"):
            for m in semua_metrik:
                if r[m] != "":
                    grup[(r["kombinasi"], kat)][m].append(float(r[m]))
    hasil = {g: {m: ringkas(v) for m, v in ms.items()} for g, ms in grup.items()}

    # tabel waktu
    baris = []
    for m, nama in METRIK_WAKTU:
        if m not in kolom:
            continue
        for kat in KATEGORI + ["Semua"]:
            baris.append([nama, kat] + [f"{angka(hasil[(k, kat)][m][0])} ± {angka(hasil[(k, kat)][m][1])}"
                                        for k in KOMBINASI])
    tulis("tabel_waktu.csv", ["Metrik (ms)", "Kategori"] + [LABEL[k] for k in KOMBINASI], baris)

    # tabel memori
    baris = []
    for m, nama in METRIK_MEMORI:
        if m not in kolom:
            continue
        for kat in KATEGORI + ["Semua"]:
            baris.append([nama, kat] + [f"{angka(hasil[(k, kat)][m][0], 1)} ± {angka(hasil[(k, kat)][m][1], 1)}"
                                        for k in KOMBINASI])
    tulis("tabel_memori.csv", ["Metrik (KB)", "Kategori"] + [LABEL[k] for k in KOMBINASI], baris)

    # tabel ukuran (byte)
    ukuran = [("kunci_ecdsa_publik_byte", "Kunci publik ECDSA"), ("kunci_ecdsa_privat_byte", "Kunci privat ECDSA"),
              ("kunci_pqc_publik_byte", "Kunci publik PQC"), ("kunci_pqc_privat_byte", "Kunci privat PQC"),
              ("sig_ecdsa_byte", "Tanda tangan ECDSA"), ("sig_pqc_byte", "Tanda tangan PQC"),
              ("paket_byte", "Paket tanda tangan (Base64)"), ("pertambahan_file_byte", "Pertambahan ukuran file")]
    nilai_ukuran = {}
    baris = []
    for m, nama in ukuran:
        if m not in kolom:
            continue
        b = [nama]
        for k in KOMBINASI:
            v = [float(r[m]) for r in data if r["kombinasi"] == k and r[m] != ""]
            mn, mk, rt = min(v), max(v), st.mean(v)
            nilai_ukuran[(k, m)] = (rt, mn, mk)
            b.append(angka(rt, 0) if mn == mk else f"{angka(rt, 1)} (min {angka(mn, 0)}, maks {angka(mk, 0)})")
        baris.append(b)
    tulis("tabel_ukuran.csv", ["Ukuran (byte)"] + [LABEL[k] for k in KOMBINASI], baris)

    buat_grafik(data, hasil, nilai_ukuran, kolom)
    print(f"Kinerja: {len(data)} baris pengukuran direkap")


# ---------------------------------------------------------------- grafik
def buat_grafik(data, hasil, ukuran, kolom):
    # 1. waktu tanda tangan murni
    fig, ax = plt.subplots(figsize=(7.5, 4))
    batang_kelompok(ax, hasil, "waktu_ttd_saja_ms", "Waktu tanda tangan (ms)")
    simpan(fig, "grafik_1_waktu_tanda_tangan.png")

    # 2. waktu verifikasi
    fig, ax = plt.subplots(figsize=(7.5, 4))
    batang_kelompok(ax, hasil, "waktu_verifikasi_ms", "Waktu verifikasi (ms)")
    simpan(fig, "grafik_2_waktu_verifikasi.png")

    # 3. komponen waktu penandatanganan (bertumpuk): hash + tanda tangan + simpan PNG
    komponen = [("waktu_hash_ms", "Hash piksel", "#c3c2b7"),
                ("waktu_ttd_saja_ms", "Tanda tangan ECDSA + PQC", "#33415c"),
                ("waktu_simpan_ms", "Simpan PNG + metadata", "#8a94a8")]
    fig, ax = plt.subplots(figsize=(9, 4.4))
    posisi, label_x = [], []
    for g, kat in enumerate(KATEGORI):
        for i, k in enumerate(KOMBINASI):
            posisi.append(g * 3.6 + i)
            label_x.append(LABEL[k].replace("ECDSA + ", "").replace("-128f", "").replace("-44", "").replace("-512", ""))
    bawah = np.zeros(len(posisi))
    for m, nama, warna in komponen:
        v = np.array([hasil[(k, kat)][m][0] for kat in KATEGORI for k in KOMBINASI])
        ax.bar(posisi, v, 0.82, bottom=bawah, color=warna, label=nama, edgecolor="white", linewidth=1)
        bawah += v
    for p, tot in zip(posisi, bawah):
        ax.annotate(angka(tot, 1), (p, tot), xytext=(0, 3), textcoords="offset points",
                    ha="center", fontsize=7, color=TINTA)
    ax.set_xticks(posisi, label_x, fontsize=7.5)
    for g, kat in enumerate(KATEGORI):
        ax.text(g * 3.6 + 1, -0.13, f"Kategori {kat}", transform=ax.get_xaxis_transform(),
                ha="center", fontsize=9, color=TINTA)
    ax.set_ylabel("Waktu penandatanganan (ms)")
    ax.legend(loc="upper left", fontsize=8)
    ax.margins(y=0.12)
    simpan(fig, "grafik_3_komponen_penandatanganan.png")

    # 4. waktu pembangkitan kunci (semua citra)
    fig, ax = plt.subplots(figsize=(6, 3.6))
    rata = [hasil[(k, "Semua")]["waktu_keygen_ms"][0] for k in KOMBINASI]
    sd = [hasil[(k, "Semua")]["waktu_keygen_ms"][1] for k in KOMBINASI]
    b = ax.bar([LABEL[k] for k in KOMBINASI], rata, 0.55, color=[WARNA[k] for k in KOMBINASI],
               yerr=sd, error_kw={"elinewidth": 0.8, "capsize": 3, "ecolor": TINTA_2})
    label_batang(ax, b, [angka(v) for v in rata], sd=sd)
    ax.set_ylabel("Waktu pembangkitan kunci (ms)")
    ax.margins(y=0.18)
    simpan(fig, "grafik_4_waktu_keygen.png")

    # 5. ukuran tanda tangan PQC dan pertambahan ukuran file
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.8))
    for ax, (m, judul) in zip(axs, [("sig_pqc_byte", "Ukuran tanda tangan PQC (byte)"),
                                    ("pertambahan_file_byte", "Pertambahan ukuran file (byte)")]):
        v = [ukuran[(k, m)][0] for k in KOMBINASI]
        b = ax.bar([LABEL[k].replace("ECDSA + ", "") for k in KOMBINASI], v, 0.55,
                   color=[WARNA[k] for k in KOMBINASI])
        label_batang(ax, b, [angka(x, 0) for x in v])
        ax.set_ylabel(judul)
        ax.margins(y=0.15)
    fig.tight_layout()
    simpan(fig, "grafik_5_ukuran.png")

    # 6. memori puncak
    if "memori_puncak_ttd_kb" in kolom:
        fig, axs = plt.subplots(1, 2, figsize=(10, 3.9), sharey=True)
        for ax, (m, judul) in zip(axs, METRIK_MEMORI):
            batang_kelompok(ax, hasil, m, "Memori puncak (KB)", des=0, sd=False)
            ax.set_title(judul, fontsize=10, color=TINTA)
            ax.legend(loc="upper left", fontsize=7, ncol=1)
        fig.tight_layout()
        simpan(fig, "grafik_6_memori.png")

    # 7. waktu verifikasi terhadap jumlah piksel (rata-rata per citra)
    per_citra = defaultdict(list)
    piksel = {}
    for r in data:
        per_citra[(r["kombinasi"], r["citra"])].append(float(r["waktu_verifikasi_ms"]))
        piksel[r["citra"]] = int(r["piksel"])
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    for k in KOMBINASI:
        xs = [piksel[c] / 1e6 for (kk, c) in per_citra if kk == k]
        ys = [st.mean(v) for (kk, c), v in per_citra.items() if kk == k]
        ax.scatter(xs, ys, s=22, color=WARNA[k], label=LABEL[k], edgecolor="white", linewidth=0.6, alpha=0.9)
    ax.set_xlabel("Jumlah piksel citra (juta piksel)")
    ax.set_ylabel("Rata-rata waktu verifikasi (ms)")
    ax.legend(loc="upper left", fontsize=8)
    format_sumbu(ax, "x")
    simpan(fig, "grafik_7_verifikasi_vs_piksel.png")


if __name__ == "__main__":
    KELUAR.mkdir(exist_ok=True)
    rekap_fungsional()
    rekap_kinerja()
    print(f"Selesai. Tabel dan grafik tersimpan di folder {KELUAR}/")