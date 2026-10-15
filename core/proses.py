"""Alur lengkap tanda tangan dan verifikasi citra, beserta pengukurannya."""

import time

import psutil

from core import citra, hybrid

_PROSES = psutil.Process()


def _memori():
    """Memori yang sedang dipakai program ini (RSS), dalam byte."""
    return _PROSES.memory_info().rss


def ukur_keygen(kombinasi):
    """Membangkitkan kunci sambil mengukur waktunya (ms)."""
    t0 = time.perf_counter()
    kunci = hybrid.bangkitkan_kunci(kombinasi)
    return kunci, (time.perf_counter() - t0) * 1000


def tandatangani_citra(img, kunci):
    """hash -> tanda tangan ECDSA dan PQC -> paket -> PNG. Mengembalikan (png_bytes, info)."""
    mem0 = _memori()
    t0 = time.perf_counter()

    nilai_hash = citra.hitung_hash(img)
    t1 = time.perf_counter()

    sig_ecdsa, sig_pqc = hybrid.tandatangani(nilai_hash, kunci)
    t2 = time.perf_counter()

    paket = citra.buat_paket(kunci["kombinasi"], sig_ecdsa, sig_pqc)
    png_bertanda = citra.simpan_png(img, paket)
    t3 = time.perf_counter()

    mem1 = _memori()

    # PNG TANPA tanda tangan, sebagai pembanding pertambahan ukuran file
    png_polos = citra.simpan_png(img)

    info = {
        "kombinasi": kunci["kombinasi"],
        "waktu_hash_ms": (t1 - t0) * 1000,
        "waktu_tanda_tangan_ms": (t2 - t1) * 1000,
        "waktu_simpan_ms": (t3 - t2) * 1000,
        "waktu_total_ms": (t3 - t0) * 1000,
        "memori_kb": max(mem1 - mem0, 0) / 1024,
        "ukuran_sig_ecdsa": len(sig_ecdsa),
        "ukuran_sig_pqc": len(sig_pqc),
        "ukuran_paket": len(paket),
        "ukuran_png_polos": len(png_polos),
        "ukuran_png_bertanda": len(png_bertanda),
        "pertambahan_file": len(png_bertanda) - len(png_polos),
    }
    return png_bertanda, info


def verifikasi_citra(img, kunci_publik_per_kombinasi):
    """Mengembalikan dict berisi 'status' (VALID / TIDAK VALID) dan 'alasan'.

    kunci_publik_per_kombinasi: {kode_kombinasi: kunci_publik}
    """
    t0 = time.perf_counter()
    hasil = {"status": "TIDAK VALID", "alasan": "", "kombinasi": None,
             "ecdsa_cocok": None, "pqc_cocok": None}

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
                cek = hybrid.verifikasi(nilai_hash, sig_ecdsa, sig_pqc, kunci_publik)
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

    hasil["waktu_verifikasi_ms"] = (time.perf_counter() - t0) * 1000
    return hasil