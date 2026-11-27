"""Bangkitkan kunci, tanda tangan, dan verifikasi hybrid (ECDSA + pasca-kuantum).

Ketiga fungsi utama menerima argumen opsional `waktu` (dict).
- Kalau `waktu` diberikan, waktu operasi ECDSA dan pasca-kuantum dicatat
  TERPISAH ke dict itu (dalam milidetik). Ini dipakai oleh uji_kinerja.py.
- Kalau `waktu` tidak diberikan, fungsi bekerja persis seperti versi lama,
  sehingga app.py dan manipulasi.py tidak perlu diubah.

Waktu yang dicatat adalah waktu operasi kriptografi "murni":
- ECDSA : hanya pemanggilan generate_private_key / sign / verify.
- PQC   : hanya pemanggilan generate_keypair / sign / verify. Pembuatan objek
          oqs.Signature (memuat kunci privat ke liboqs) TIDAK ikut dihitung.

Kurva ECDSA dibaca dari kombinasi.py (kolom "ecdsa"). Kalau kolom itu tidak
ada, dipakai P-256. Dengan kombinasi.py yang sekarang, semuanya tetap P-256.
"""

import time

import oqs
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed

from core.kombinasi import KOMBINASI

# Hash sudah dihitung di citra.py, jadi ECDSA diberi tahu bahwa data yang
# masuk sudah berupa hash SHA-256 (32 byte) dan tidak di-hash ulang.
ECDSA_ALGO = ec.ECDSA(Prehashed(hashes.SHA256()))

KURVA_ECDSA = {"P-256": ec.SECP256R1, "P-384": ec.SECP384R1, "P-521": ec.SECP521R1}
KURVA_BAKU = "P-256"


def _ms(t0):
    """Selisih waktu sejak t0, dalam milidetik."""
    return (time.perf_counter() - t0) * 1000


def nama_kurva(kombinasi):
    """Nama kurva ECDSA untuk kombinasi ini (default P-256)."""
    return KOMBINASI[kombinasi].get("ecdsa", KURVA_BAKU)


def bangkitkan_kunci(kombinasi, waktu=None):
    nama_pqc = KOMBINASI[kombinasi]["pqc"]
    kurva = KURVA_ECDSA[nama_kurva(kombinasi)]

    t0 = time.perf_counter()
    ecdsa_privat = ec.generate_private_key(kurva())
    t_ecdsa = _ms(t0)

    with oqs.Signature(nama_pqc) as pqc:
        t0 = time.perf_counter()
        pqc_publik = pqc.generate_keypair()
        t_pqc = _ms(t0)
        pqc_privat = pqc.export_secret_key()

    if waktu is not None:
        waktu["keygen_ecdsa_ms"] = t_ecdsa
        waktu["keygen_pqc_ms"] = t_pqc

    return {
        "kombinasi": kombinasi,
        "ecdsa_privat": ecdsa_privat,
        "ecdsa_publik": ecdsa_privat.public_key(),
        "pqc_privat": pqc_privat,
        "pqc_publik": pqc_publik,
    }


def kunci_publik_dari(kunci):
    return {
        "kombinasi": kunci["kombinasi"],
        "ecdsa_publik": kunci["ecdsa_publik"],
        "pqc_publik": kunci["pqc_publik"],
    }


def tandatangani(hash_citra, kunci, waktu=None):
    """Nilai hash yang SAMA ditandatangani terpisah oleh ECDSA dan PQC."""
    t0 = time.perf_counter()
    sig_ecdsa = kunci["ecdsa_privat"].sign(hash_citra, ECDSA_ALGO)
    t_ecdsa = _ms(t0)

    nama_pqc = KOMBINASI[kunci["kombinasi"]]["pqc"]
    with oqs.Signature(nama_pqc, secret_key=kunci["pqc_privat"]) as pqc:
        t0 = time.perf_counter()
        sig_pqc = pqc.sign(hash_citra)
        t_pqc = _ms(t0)

    if waktu is not None:
        waktu["ttd_ecdsa_ms"] = t_ecdsa
        waktu["ttd_pqc_ms"] = t_pqc

    return sig_ecdsa, sig_pqc


def verifikasi(hash_citra, sig_ecdsa, sig_pqc, kunci_publik, waktu=None):
    # Cek ECDSA
    t0 = time.perf_counter()
    try:
        kunci_publik["ecdsa_publik"].verify(sig_ecdsa, hash_citra, ECDSA_ALGO)
        ecdsa_ok = True
    except InvalidSignature:
        ecdsa_ok = False
    t_ecdsa = _ms(t0)

    # Cek PQC (tetap dicek walaupun ECDSA gagal, supaya alasan TIDAK VALID lengkap)
    nama_pqc = KOMBINASI[kunci_publik["kombinasi"]]["pqc"]
    with oqs.Signature(nama_pqc) as pqc:
        t0 = time.perf_counter()
        pqc_ok = pqc.verify(hash_citra, sig_pqc, kunci_publik["pqc_publik"])
        t_pqc = _ms(t0)

    if waktu is not None:
        waktu["verifikasi_ecdsa_ms"] = t_ecdsa
        waktu["verifikasi_pqc_ms"] = t_pqc

    # Aturan AND: VALID hanya jika kedua tanda tangan cocok
    return {"ecdsa": ecdsa_ok, "pqc": pqc_ok, "valid": ecdsa_ok and pqc_ok}