"""
Verifica que paquete_v2/ no fue modificado: compara el SHA-256 de cada archivo con
paquete_v2/MANIFIESTO_SHA256.json. Uso: python scripts/verify_package.py
Termina con código 0 si todo coincide y 1 si algo falta o cambió.
"""
import hashlib
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "paquete_v2"


def main() -> int:
    manifest = json.loads((PKG / "MANIFIESTO_SHA256.json").read_text(encoding="utf-8"))
    bad = []
    for rel, expected in manifest.items():
        path = PKG / rel
        if not path.is_file():
            bad.append(f"FALTA     {rel}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            bad.append(f"CAMBIÓ    {rel}")
    for line in bad:
        print(line)
    print(f"{len(manifest) - len(bad)}/{len(manifest)} archivos coinciden con el manifiesto.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
