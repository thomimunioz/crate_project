# -*- coding: utf-8 -*-
"""Un solo comando para todo. Antes habia que acordarse de veinte scripts.

    crate                 levanta la app y abre el navegador  (lo de siempre)
    crate hotlist         arma la tanda de la semana
    crate veta            mina la base para PIANO / DARK / FOLK
    crate veta PIANO      una sola
    crate cavar DARK      sale a YouTube a buscar material nuevo
    crate build           regenera mi-crate.html desde crate.db
    crate sync            vuelca lo que votaste en el navegador a crate.db
    crate estado          que hay en la base, en una pantalla
    crate limpiar         saca canales de IA y arregla años de reedicion

Cada subcomando es uno de los scripts de siempre: esto no agrega logica, solo
evita tener que acordarse de cual era.
"""
import os
import subprocess
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB = r"G:\Thomi - Mi Carpeta\crate_project\crate.db"
PY = sys.executable

COMANDOS = {
    "hotlist": ["hotlist.py"],
    "veta":    ["veta.py"],
    "cavar":   ["cavar.py"],
    "build":   ["app_build.py"],
    "sync":    ["bd_sync.py"],
    "check":   ["app_check.py"],
}


def correr(script, resto):
    return subprocess.call([PY, os.path.join(HERE, script)] + resto)


def estado():
    con = sqlite3.connect(DB)
    q = lambda s: con.execute(s).fetchone()[0]
    print("CRATE")
    print("  temas en la base      %7d" % q("SELECT count(*) FROM tema"))
    print("  en tus listas         %7d" % q("SELECT count(DISTINCT id) FROM en_playlist"))
    print("  puntuados             %7d" % q("SELECT count(DISTINCT id) FROM marca WHERE estrellas>0"))
    print("  analizados (BPM/tono) %7d" % q("SELECT count(*) FROM analisis"))
    try:
        print("  esperandote en hot    %7d" % q("SELECT count(*) FROM hot"))
    except sqlite3.OperationalError:
        print("  esperandote en hot          -   (corre: crate hotlist)")
    print()
    print("  tus listas:")
    for p, n in con.execute("""SELECT playlist, count(*) FROM en_playlist
                               GROUP BY playlist ORDER BY 2 DESC"""):
        print("     %-12s %4d" % (p, n))
    con.close()
    return 0


def limpiar():
    print("== canales de IA ==")
    correr("anti_ia.py", [])
    print("\n== años de reedicion ==")
    return correr("anio_real.py", [])


def main():
    args = sys.argv[1:]
    if not args:
        return correr("crate_server.py", [])
    cmd, resto = args[0].lower(), args[1:]
    if cmd in ("estado", "status"):
        return estado()
    if cmd == "limpiar":
        return limpiar()
    if cmd in COMANDOS:
        return correr(COMANDOS[cmd][0], resto)
    if cmd in ("-h", "--help", "ayuda", "help"):
        print(__doc__)
        return 0
    print("no conozco '%s'. Probá: crate ayuda" % cmd)
    return 1


if __name__ == "__main__":
    sys.exit(main())
