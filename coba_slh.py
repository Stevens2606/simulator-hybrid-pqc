import hashlib
import oqs

print("liboqs        :", oqs.oqs_version())
print("liboqs-python :", oqs.oqs_python_version())
print()

h = hashlib.sha256(b"uji").digest()

for nama in ["ML-DSA-44", "SLH_DSA_PURE_SHA2_128F", "SLH_DSA_PURE_SHA2_128S", "SLH_DSA_PURE_SHAKE_128F"]:
    try:
        # Cara A: tanda tangan dan kunci di objek yang SAMA (tanpa ekspor kunci privat)
        with oqs.Signature(nama) as s:
            pk = s.generate_keypair()
            sig = s.sign(h)
            cara_a = s.verify(h, sig, pk)

        # Cara B: kunci privat diekspor lalu diimpor lagi (seperti di hybrid.py)
        with oqs.Signature(nama) as s:
            pk = s.generate_keypair()
            sk = s.export_secret_key()
        with oqs.Signature(nama, secret_key=sk) as s:
            sig = s.sign(h)
        with oqs.Signature(nama) as v:
            cara_b = v.verify(h, sig, pk)

        print(f"{nama:26} Cara A: {cara_a}   Cara B: {cara_b}")
    except Exception as e:
        print(f"{nama:26} ERROR: {e}")