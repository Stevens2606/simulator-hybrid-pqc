# Simulator Hybrid Post-Quantum Digital Signature untuk Integritas Citra Medis

> ⚠️ README sementara — masih dalam pengembangan (Tugas Akhir).

Simulator berbasis web untuk memperagakan dan menguji **tanda tangan digital hybrid**
(ECDSA P-256 + satu algoritma pasca-kuantum) pada citra rontgen dada.
Citra dinyatakan **VALID** hanya jika **kedua tanda tangan cocok** (aturan AND).

Tugas Akhir D3 Teknologi Informasi, Institut Teknologi Del — Kelompok 17
- Steven Simanjuntak
- Tiur Juliana Sitorus
- Maria Christin Gurning

Pembimbing: Togu Novriansyah Turnip, S.S.T., M.I.M.

---

## Cara kerja singkat

**Penandatanganan (pengirim)**
1. Citra JPEG dibaca menjadi nilai piksel.
2. Dihitung hash SHA-256 dari lebar, tinggi, dan seluruh piksel.
3. Hash ditandatangani dua kali: ECDSA P-256 (σ1) dan algoritma pasca-kuantum (σ2).
4. Kedua tanda tangan dikemas sebagai paket JSON (Base64) dan disimpan di
   chunk tEXt PNG dengan kata kunci `HybridSignature`. Piksel tidak berubah.

**Verifikasi (penerima)**
1. Paket dibaca dari chunk tEXt (jika tidak ada/rusak → TIDAK VALID).
2. Hash dihitung ulang dari citra yang diterima.
3. σ1 dan σ2 diperiksa dengan kunci publik masing-masing.
4. VALID hanya jika keduanya cocok.

## Kombinasi yang diuji (17)

ECDSA P-256 dipasangkan dengan:

| Algoritma | Varian | Level NIST |
|---|---|---|
| ML-DSA | 44 / 65 / 87 | 2 / 3 / 5 |
| Falcon | 512 / 1024 | 1 / 5 |
| SLH-DSA (SHA2 dan SHAKE, jenis f dan s) | 128 / 192 / 256 | 1 / 3 / 5 |

Daftar lengkap ada di `core/kombinasi.py`.

## Halaman simulator

| Halaman | Fungsi |
|---|---|
| Sign Image | Unggah JPEG, pilih kombinasi, hasilkan PNG bertanda tangan |
| Status and Verification | Simulasi pengirim → perjalanan → penerima, dengan atau tanpa manipulasi |
| External File Verification | Verifikasi file PNG dari luar simulator |
| Performance Comparison | Perbandingan waktu dan ukuran antarkombinasi pada sesi |

Antarmuka berbahasa Inggris. Data hanya disimpan selama sesi (tanpa basis data).

## Struktur folder

```
simulator_hybrid/
├── app.py                 # aplikasi Flask (simulator web)
├── core/
│   ├── kombinasi.py       # daftar 17 kombinasi hybrid
│   ├── hybrid.py          # pembangkitan kunci, tanda tangan, verifikasi
│   ├── citra.py           # baca citra, hitung hash, paket JSON, simpan PNG
│   ├── manipulasi.py      # skenario manipulasi citra dan tanda tangan
│   └── proses.py          # proses penandatanganan/verifikasi + pengukuran waktu
├── templates/             # tampilan HTML (Bootstrap 5)
├── uji_fungsional.py      # pengujian fungsional
├── uji_kinerja.py         # pengujian kinerja
└── hasil_uji_*.csv        # hasil pengujian
```

## Lingkungan

Wajib dijalankan di **WSL2 Ubuntu** (pada percobaan awal, verifikasi SLH-DSA
tidak berjalan benar saat dijalankan langsung di Windows).

| Perangkat lunak | Versi |
|---|---|
| Python | 3.14 |
| Flask | 3.1 |
| liboqs / liboqs-python | 0.16.0 / 0.16.0.1 |
| cryptography | 50.0.2 |
| Pillow / NumPy | 12.3.0 / 2.5.4 |
| Bootstrap / Bootstrap Icons (CDN) | 5.3.3 / 1.11.3 |

## Menjalankan simulator

```bash
cd /mnt/d/Perkuliahan/TA/simulator_hybrid
source venv-wsl/bin/activate
python app.py
```

Buka `http://127.0.0.1:5000` di browser (perlu internet untuk Bootstrap).

## Menjalankan pengujian

```bash
python uji_fungsional.py
python uji_kinerja.py 3 2          # uji coba singkat: 3 citra × 2 ulangan
python uji_kinerja.py              # pengujian penuh: 90 citra × 10 ulangan
python uji_kinerja.py 90 10 lanjut # melanjutkan bila terhenti
```

Saat pengukuran kinerja: laptop terhubung ke pengisi daya dan aplikasi lain
ditutup (end task).

## Dataset

Chest X-Ray Images (Pneumonia), Kaggle — 90 citra sampel
(30 Kecil, 30 Sedang, 30 Besar, seed 42).