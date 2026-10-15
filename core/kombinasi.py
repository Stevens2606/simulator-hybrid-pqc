# Daftar tiga kombinasi hybrid yang dibandingkan.
# ECDSA selalu sama (P-256) sebagai variabel kontrol.
# Yang berbeda hanya algoritma pasca-kuantumnya (PQC).

KOMBINASI = {
    "ECDSA-P256+ML-DSA-44": {
        "label": "ECDSA P-256 + ML-DSA-44",
        "pqc": "ML-DSA-44",
        "level_nist": 2,
    },
    "ECDSA-P256+Falcon-512": {
        "label": "ECDSA P-256 + Falcon-512",
        "pqc": "Falcon-512",
        "level_nist": 1,
    },
    "ECDSA-P256+SLH-DSA-SHA2-128f": {
        "label": "ECDSA P-256 + SLH-DSA-SHA2-128f",
        "pqc": "SLH_DSA_PURE_SHA2_128F",
        "level_nist": 1,
    },
}


def daftar_kombinasi():
    """Mengembalikan daftar (id, label) untuk ditampilkan di form web."""
    return [(kode, data["label"]) for kode, data in KOMBINASI.items()]