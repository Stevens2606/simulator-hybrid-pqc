"""Mencatat spesifikasi perangkat dan versi pustaka untuk subbab 3.5.3.

Cara pakai (di WSL, venv-wsl aktif, dari folder simulator_hybrid):
    python cek_lingkungan.py
"""

import platform
import ssl
import subprocess
from importlib.metadata import PackageNotFoundError, version

import oqs
import psutil


def baca(path, kunci):
    try:
        with open(path) as f:
            for baris in f:
                if baris.startswith(kunci):
                    return baris.split(":", 1)[1].strip()
    except OSError:
        pass
    return "-"


def jalankan(perintah):
    try:
        return subprocess.run(perintah, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "-"


print("=== Perangkat keras (yang terlihat dari WSL) ===")
print("Prosesor        :", baca("/proc/cpuinfo", "model name"))
print("Inti fisik      :", psutil.cpu_count(logical=False))
print("Thread (logis)  :", psutil.cpu_count(logical=True))
print(f"RAM untuk WSL   : {psutil.virtual_memory().total / 1024**3:.2f} GB")

print("\n=== Sistem operasi ===")
print("Ubuntu (WSL2)   :", jalankan(["lsb_release", "-ds"]))
print("Kernel          :", platform.release())

print("\n=== Bahasa dan kompiler ===")
print("Python          :", platform.python_version())
print("GCC             :", jalankan(["gcc", "-dumpfullversion"]))
print("OpenSSL         :", ssl.OPENSSL_VERSION)

print("\n=== Pustaka ===")
print("liboqs (C)      :", oqs.oqs_version())
for paket in ["liboqs-python", "cryptography", "Flask", "Pillow", "numpy", "psutil", "matplotlib"]:
    try:
        print(f"{paket:16s}:", version(paket))
    except PackageNotFoundError:
        print(f"{paket:16s}: tidak terpasang")