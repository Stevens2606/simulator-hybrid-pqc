# Daftar kombinasi hybrid yang dibandingkan.
# ECDSA selalu sama (P-256) sebagai variabel kontrol.
# Yang berbeda adalah algoritma pasca-kuantum (PQC) dan tingkat keamanannya.
#
# Setiap algoritma PQC dipakai pada semua level dan varian yang tersedia:
#   ML-DSA  : level 2, 3, 5 (tidak ada level 1)
#   Falcon  : level 1, 5    (tidak ada level 3)
#   SLH-DSA : level 1, 3, 5, fungsi hash SHA2 dan SHAKE, jenis f (fast) dan s (small)
#
# Untuk menambah kombinasi baru, cukup tambahkan satu entri baru
# di KOMBINASI dengan format yang sama.


def _slh(hash_, level_bit, jenis, level_nist):
    """Membuat satu entri SLH-DSA. Contoh: _slh("SHA2", 128, "f", 1)."""
    kode = f"ECDSA-P256+SLH-DSA-{hash_}-{level_bit}{jenis}"
    return kode, {
        "label": f"ECDSA P-256 + SLH-DSA-{hash_}-{level_bit}{jenis}",
        "pqc": f"SLH_DSA_PURE_{hash_}_{level_bit}{jenis.upper()}",
        "algoritma": f"SLH-DSA-{hash_}-{jenis}",
        "level_nist": level_nist,
    }


KOMBINASI = {
    # ---------------- ML-DSA (FIPS 204)
    "ECDSA-P256+ML-DSA-44": {
        "label": "ECDSA P-256 + ML-DSA-44",
        "pqc": "ML-DSA-44",
        "algoritma": "ML-DSA",
        "level_nist": 2,
    },
    "ECDSA-P256+ML-DSA-65": {
        "label": "ECDSA P-256 + ML-DSA-65",
        "pqc": "ML-DSA-65",
        "algoritma": "ML-DSA",
        "level_nist": 3,
    },
    "ECDSA-P256+ML-DSA-87": {
        "label": "ECDSA P-256 + ML-DSA-87",
        "pqc": "ML-DSA-87",
        "algoritma": "ML-DSA",
        "level_nist": 5,
    },
    # ---------------- Falcon (FN-DSA, draft FIPS 206)
    "ECDSA-P256+Falcon-512": {
        "label": "ECDSA P-256 + Falcon-512",
        "pqc": "Falcon-512",
        "algoritma": "Falcon",
        "level_nist": 1,
    },
    "ECDSA-P256+Falcon-1024": {
        "label": "ECDSA P-256 + Falcon-1024",
        "pqc": "Falcon-1024",
        "algoritma": "Falcon",
        "level_nist": 5,
    },
}

# ---------------- SLH-DSA (FIPS 205): 2 hash x 2 jenis x 3 level = 12 varian
for _hash in ("SHA2", "SHAKE"):
    for _jenis in ("f", "s"):
        for _bit, _level in ((128, 1), (192, 3), (256, 5)):
            _kode, _data = _slh(_hash, _bit, _jenis, _level)
            KOMBINASI[_kode] = _data


def daftar_kombinasi():
    """Mengembalikan daftar (id, label) untuk ditampilkan di form web."""
    return [(kode, data["label"]) for kode, data in KOMBINASI.items()]