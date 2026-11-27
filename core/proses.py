"""Alur lengkap tanda tangan dan verifikasi citra, beserta pengukuran waktunya.

Dipakai bersama oleh simulator (app.py) dan script pengujian (uji_kinerja.py).
Semua waktu dalam milidetik (ms), diukur dengan time.perf_counter().
"""

import time

from core import citra, hybrid


def _ms(t_awal, t_akhir):
    return (t_akhir - t_awal) * 1000


def ukur_keygen_rinci(kombinasi):
    """Bangkitkan kunci; kembalikan (kunci, rincian waktu ECDSA, PQC, dan total)."""
    rinci = {}
    t0 = time.perf_counter()
    kunci = hybrid.bangkitkan_kunci(kombinasi, waktu=rinci)
    rinci["keygen_total_ms"] = _ms(t0, time.perf_counter())
    return kunci, rinci


def ukur_keygen(kombinasi):
    """Versi lama (dipakai app.py): kembalikan (kunci, waktu total ms)."""
    kunci, rinci = ukur_keygen_rinci(kombinasi)
    return kunci, rinci["keygen_total_ms"]


def tandatangani_citra(img, kunci):
    """hash -> tanda tangan ECDSA dan PQC -> paket JSON -> disisipkan ke JPEG.

    img harus dibuka dengan citra.buka_citra() dari file JPEG.
    Mengembalikan (jpeg_bertanda_bytes, info).
    """
    t0 = time.perf_counter()

    nilai_hash = citra.hitung_hash(img)
    t1 = time.perf_counter()

    rinci = {}
    sig_ecdsa, sig_pqc = hybrid.tandatangani(nilai_hash, kunci, waktu=rinci)
    t2 = time.perf_counter()

    paket = citra.buat_paket(kunci["kombinasi"], sig_ecdsa, sig_pqc)
    jpeg_bertanda = citra.simpan_citra(img, paket)
    t3 = time.perf_counter()

    # JPEG TANPA paket, sebagai pembanding pertambahan ukuran file (tidak ikut diukur waktunya)
    ukuran_asli = citra.ukuran_tanpa_paket(img)

    info = {
        "kombinasi": kunci["kombinasi"],
        "waktu_hash_ms": _ms(t0, t1),
        "waktu_ttd_ecdsa_ms": rinci["ttd_ecdsa_ms"],      # ECDSA murni
        "waktu_ttd_pqc_ms": rinci["ttd_pqc_ms"],          # pasca-kuantum murni
        "waktu_tanda_tangan_ms": _ms(t1, t2),             # seluruh langkah tanda tangan hybrid
        "waktu_simpan_ms": _ms(t2, t3),                   # buat paket JSON + sisipkan ke JPEG
        "waktu_total_ms": _ms(t0, t3),                    # hash sampai JPEG bertanda jadi
        "ukuran_sig_ecdsa": len(sig_ecdsa),
        "ukuran_sig_pqc": len(sig_pqc),
        "ukuran_paket": len(paket),
        "ukuran_file_asli": ukuran_asli,
        "ukuran_file_bertanda": len(jpeg_bertanda),
        "pertambahan_file": len(jpeg_bertanda) - ukuran_asli,
    }
    return jpeg_bertanda, info


def verifikasi_citra(img, kunci_publik_per_kombinasi):
    """Mengembalikan dict berisi 'status' (VALID / TIDAK VALID), 'alasan', dan waktu.

    kunci_publik_per_kombinasi: {kode_kombinasi: kunci_publik}
    Waktu rinci (baca+hash, ECDSA, PQC) bernilai None bila tanda tangan tidak sempat dicek.
    """
    t0 = time.perf_counter()
    hasil = {"status": "TIDAK VALID", "alasan": "", "kombinasi": None,
             "ecdsa_cocok": None, "pqc_cocok": None,
             "waktu_baca_hash_ms": None, "waktu_cek_ttd_ms": None,
             "waktu_verifikasi_ecdsa_ms": None, "waktu_verifikasi_pqc_ms": None}

    paket = citra.baca_paket(img)

    if paket is None:
        hasil["alasan"] = "Tanda tangan tidak ditemukan pada citra."
    else:
        try:
            kombinasi, sig_ecdsa, sig_pqc = citra.urai_paket(paket)
        except Exception:
            kombinasi = None
            hasil["alasan"] = "Paket tanda tangan rusak atau tidak lengkap."

        if kombinasi is not None:
            hasil["kombinasi"] = kombinasi
            kunci_publik = kunci_publik_per_kombinasi.get(kombinasi)

            if kunci_publik is None:
                hasil["alasan"] = "Kunci publik untuk kombinasi ini tidak tersedia."
            else:
                nilai_hash = citra.hitung_hash(img)
                t1 = time.perf_counter()

                rinci = {}
                cek = hybrid.verifikasi(nilai_hash, sig_ecdsa, sig_pqc, kunci_publik, waktu=rinci)
                t2 = time.perf_counter()

                hasil["waktu_baca_hash_ms"] = _ms(t0, t1)          # baca paket + urai + hitung hash ulang
                hasil["waktu_cek_ttd_ms"] = _ms(t1, t2)            # seluruh langkah cek dua tanda tangan
                hasil["waktu_verifikasi_ecdsa_ms"] = rinci["verifikasi_ecdsa_ms"]
                hasil["waktu_verifikasi_pqc_ms"] = rinci["verifikasi_pqc_ms"]
                hasil["ecdsa_cocok"] = cek["ecdsa"]
                hasil["pqc_cocok"] = cek["pqc"]

                if cek["valid"]:
                    hasil["status"] = "VALID"
                    hasil["alasan"] = "Citra asli dan tidak berubah sejak ditandatangani."
                elif not cek["ecdsa"] and not cek["pqc"]:
                    hasil["alasan"] = "Kedua tanda tangan tidak cocok: citra telah berubah atau tanda tangan tidak sah."
                else:
                    gagal = "ECDSA" if not cek["ecdsa"] else "pasca-kuantum"
                    hasil["alasan"] = f"Tanda tangan {gagal} tidak cocok."

    hasil["waktu_verifikasi_ms"] = _ms(t0, time.perf_counter())   # total verifikasi
    return hasil