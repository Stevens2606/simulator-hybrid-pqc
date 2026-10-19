"""Mengecek isi folder core: fungsi apa saja yang ada dan parameternya.

Tidak mengubah apa pun, hanya menampilkan informasi.
Cara pakai (di WSL, venv-wsl aktif, dari folder simulator_hybrid):
    python cek_core.py
"""

import inspect
from pathlib import Path

from core import citra, hybrid, kombinasi, manipulasi, proses

for modul in (kombinasi, hybrid, citra, proses, manipulasi):
    path = Path(modul.__file__)
    print(f"=== core/{path.name} ({sum(1 for _ in open(path, encoding='utf-8'))} baris) ===")
    for nama, obj in inspect.getmembers(modul):
        if nama.startswith("_"):
            continue
        if inspect.isfunction(obj) and obj.__module__ == modul.__name__:
            print(f"  fungsi {nama}{inspect.signature(obj)}")
        elif inspect.isclass(obj) and obj.__module__ == modul.__name__:
            print(f"  class  {nama}")
        elif isinstance(obj, dict) and nama.isupper():
            print(f"  data   {nama}: {list(obj.keys())}")
    print()