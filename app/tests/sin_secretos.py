# -*- coding: utf-8 -*-
"""Frena el commit si hay un secreto versionado.

Es el mismo guardia que corre en el CI, pero ANTES de que el commit exista:
una clave que entra al historial de git ya no sale sin reescribir el
historial entero. Mas vale pararla aca.

Se usa solo, via .pre-commit-config.yaml, o a mano:
    python app/tests/sin_secretos.py
"""
import re
import subprocess
import sys

PELIGROSO = re.compile(
    r"(^|/)\.env$|slskd_key|\.pem$|\.key$|credentials|id_rsa|\.pfx$")


def main():
    r = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
    malos = [f for f in r.stdout.splitlines() if PELIGROSO.search(f)]
    if malos:
        print("NO se puede commitear: hay secretos versionados")
        for m in malos:
            print("   %s" % m)
        print()
        print("sacalos con:  git rm --cached <archivo>   y agregalos al .gitignore")
        return 1
    print("sin secretos versionados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
