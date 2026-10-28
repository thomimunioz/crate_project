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
    crate slsk            prende solo slskd (si se te cayo)
    crate abrir           lo que usa el acceso directo: prende todo y abre
    crate parar           apaga todo (servidor + soulseek)

Cada subcomando es uno de los scripts de siempre: esto no agrega logica, solo
evita tener que acordarse de cual era.
"""
import os
import socket
import time
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


RAIZ = os.path.dirname(HERE)
SLSKD = os.path.join(RAIZ, "slskd")
PUERTO = 7777


def puerto_abierto(puerto, host="127.0.0.1"):
    with socket.socket() as s:
        s.settimeout(0.4)
        return s.connect_ex((host, puerto)) == 0


def levantar_slskd():
    """slskd es un programa aparte: si no esta prendido, el boton de Soulseek
    tira "no se puede establecer una conexion" y no se entiende por que. Como
    siempre hay que prenderlo igual, lo prende esto.

    Tarda ~10s en loguearse a la red de Soulseek, pero no bloqueamos: para
    cuando Thomas apriete el boton de buscar ya va a estar.
    """
    if puerto_abierto(5030):
        return "ya estaba prendido"
    exe = os.path.join(SLSKD, "slskd.exe")
    if not os.path.exists(exe):
        return "no esta instalado (bajalo de github.com/slskd/slskd)"
    try:
        subprocess.Popen([exe, "--config", os.path.join(SLSKD, "slskd.yml")],
                         cwd=SLSKD, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        return "prendido (tarda ~10s en conectarse a la red)"
    except Exception as e:
        return "no pude prenderlo: %s" % str(e)[:60]


def abrir():
    """Lo que hace el acceso directo de la barra de tareas.

    Tiene que servir tanto si no hay nada prendido como si la app ya esta
    corriendo: en ese caso no levanta un segundo servidor, solo trae la
    ventana. Y espera a que el puerto conteste antes de abrir el navegador,
    porque si no Chrome muestra "no se puede acceder" y hay que recargar.
    """
    import webbrowser
    levantar_slskd()
    if not puerto_abierto(PUERTO):
        pyw = os.path.join(os.path.dirname(PY), "pythonw.exe")
        exe = pyw if os.path.exists(pyw) else PY       # sin consola negra
        subprocess.Popen([exe, os.path.join(HERE, "crate_server.py"),
                          "--sin-navegador"], cwd=HERE,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):                            # hasta 15 s
            if puerto_abierto(PUERTO):
                break
            time.sleep(0.25)
        else:
            print("el servidor no arranco")
            return 1
    webbrowser.open("http://127.0.0.1:%d/mi-crate.html" % PUERTO)
    return 0


def parar():
    """Apaga TODO lo que prende `crate`: el servidor y slskd.

    Cerrar la pestaña del navegador no apaga nada —el servidor no tiene
    ventana— y slskd se queda conectado a la red de Soulseek ocupando 166 MB.
    Si "parar" dejara slskd prendido no estaria parando nada en la practica.

    No alcanza con mirar el puerto: pueden quedar procesos vivos que NO lo
    tienen. Si se mira solo el puerto y esta cerrado, se contesta "no estaba
    prendido" y los huerfanos siguen ahi.
    """
    # Ojo con el filtro: si se busca solo por linea de comando, el PowerShell
    # que hace la consulta TAMBIEN la contiene (esta en su propio comando) y
    # se cuenta —y se intenta matar— a si mismo. Por eso se exige ademas que
    # el proceso sea python. Costo media hora de numeros inflados el 28-oct.
    ps_srv = ("Get-CimInstance Win32_Process | Where-Object { "
              "$_.Name -like 'python*' -and "
              "$_.CommandLine -like '*crate_server*' } | "
              "ForEach-Object { $_.ProcessId }")
    ps_slsk = "Get-Process slskd -ErrorAction SilentlyContinue | % { $_.Id }"

    def pids(cmd):
        return subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                              capture_output=True, text=True).stdout.split()

    srv, slsk = pids(ps_srv), pids(ps_slsk)
    if not srv and not slsk:
        print("no habia nada prendido")
        return 0
    for cmd in (ps_srv, ps_slsk):
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        cmd + " | ForEach-Object { Stop-Process -Id $_ -Force }"],
                       capture_output=True, text=True)
    time.sleep(1.0)
    q_srv, q_slsk = pids(ps_srv), pids(ps_slsk)
    print("servidor: %s" % ("apagado" if not q_srv else "sigue vivo"))
    print("soulseek: %s" % ("apagado" if not q_slsk else "sigue vivo"))
    return 1 if (q_srv or q_slsk) else 0


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
        print("soulseek: %s" % levantar_slskd())
        return correr("crate_server.py", [])
    cmd, resto = args[0].lower(), args[1:]
    if cmd in ("estado", "status"):
        return estado()
    if cmd == "limpiar":
        return limpiar()
    if cmd == "abrir":
        return abrir()
    if cmd in ("parar", "apagar", "stop"):
        return parar()
    if cmd in ("slsk", "soulseek"):
        print("soulseek: %s" % levantar_slskd())
        return 0
    if cmd in COMANDOS:
        return correr(COMANDOS[cmd][0], resto)
    if cmd in ("-h", "--help", "ayuda", "help"):
        print(__doc__)
        return 0
    print("no conozco '%s'. Probá: crate ayuda" % cmd)
    return 1


if __name__ == "__main__":
    sys.exit(main())
