"""Bangkitkan kunci, tanda tangan, dan verifikasi hybrid (ECDSA P-256 + PQC)."""

import oqs
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed

from core.kombinasi import KOMBINASI

# Hash sudah dihitung di citra.py, jadi ECDSA diberi tahu bahwa data sudah berupa hash SHA-256
ECDSA_ALGO = ec.ECDSA(Prehashed(hashes.SHA256()))


def bangkitkan_kunci(kombinasi):
    nama_pqc = KOMBINASI[kombinasi]["pqc"]

    ecdsa_privat = ec.generate_private_key(ec.SECP256R1())  # SECP256R1 = P-256

    with oqs.Signature(nama_pqc) as pqc:
        pqc_publik = pqc.generate_keypair()
        pqc_privat = pqc.export_secret_key()

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


def tandatangani(hash_citra, kunci):
    sig_ecdsa = kunci["ecdsa_privat"].sign(hash_citra, ECDSA_ALGO)

    nama_pqc = KOMBINASI[kunci["kombinasi"]]["pqc"]
    with oqs.Signature(nama_pqc, secret_key=kunci["pqc_privat"]) as pqc:
        sig_pqc = pqc.sign(hash_citra)

    return sig_ecdsa, sig_pqc


def verifikasi(hash_citra, sig_ecdsa, sig_pqc, kunci_publik):
    # Cek ECDSA
    try:
        kunci_publik["ecdsa_publik"].verify(sig_ecdsa, hash_citra, ECDSA_ALGO)
        ecdsa_ok = True
    except InvalidSignature:
        ecdsa_ok = False

    # Cek PQC (tetap dicek walaupun ECDSA gagal, supaya alasan TIDAK VALID lengkap)
    nama_pqc = KOMBINASI[kunci_publik["kombinasi"]]["pqc"]
    with oqs.Signature(nama_pqc) as pqc:
        pqc_ok = pqc.verify(hash_citra, sig_pqc, kunci_publik["pqc_publik"])

    # Aturan AND
    return {"ecdsa": ecdsa_ok, "pqc": pqc_ok, "valid": ecdsa_ok and pqc_ok}