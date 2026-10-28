# -*- coding: utf-8 -*-
"""Encuentra diggers NUEVOS dejando que los discos los delaten.

Thomas, 28-oct: "no quiero limitarme a un canal. Porque nos ata a lo que esa
persona consuma o crea que está bueno. Hay muchos otros diggers por ahi."

Tiene razon, y mirar solo los canales medidos es morderse la cola: solo
podemos medir los que ya cavamos. La vuelta es al reves — en vez de buscar
canales, se buscan las OBRAS que el ya marco con 4 o 5 estrellas y se mira
quien mas las subio. Alguien que tiene cinco de sus joyas esta cavando la
misma veta; alguien que tiene una, es casualidad.

Por eso hace falta volumen. Con seis joyas todos los canales aparecen una vez
y no se distingue un digger de un tipo que subio un tema suelto (probado el
28-oct). Con cuarenta, los que repiten se separan solos.

Cero quota: yt-dlp, igual que el resto del proyecto.

Uso:
    python diggers.py              sobre todas tus joyas (tarda unos minutos)
    python diggers.py --n=20       mas rapido, menos señal
    python diggers.py --guardar    anota los hallazgos en canal_descubierto
"""
import os
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import criterios
import crate_server as srv

DB = r"G:\Thomi - Mi Carpeta\crate_project\crate.db"
N = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--n=")), "40"))
GUARDAR = "--guardar" in sys.argv

# Canales que aparecen buscando soul viejo pero no son diggers: musica
# funcional, recopilados de algoritmo, radios. Ensucian el conteo.
BASURA_CANAL = criterios.rx(
    "focus", "heal", "healing", "relax", "relaxing", "study", "sleep",
    "meditation", "lofi", "lo-fi", "ambience", "ambient music", "playlist",
    "mix", "radio", "topic", "vevo", "official", "records official")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS canal_descubierto(
  canal     TEXT PRIMARY KEY,
  joyas     INTEGER,       -- cuantas de sus 4-5 estrellas tiene
  ejemplo   TEXT,          -- un video suyo, para poder llegar al canal
  visto     TEXT,
  cavado    TEXT           -- cuando se cavo, si se cavo
);
"""


def util(canal):
    """Si vale la pena mirarlo: ni conocido, ni basura."""
    if not canal:
        return False
    if canal in criterios.CANALES or canal in criterios.CANAL_GEN:
        return False
    if canal in getattr(criterios, "VETADOS", set()):
        return False
    return not BASURA_CANAL.search(canal)


def cavar_canal(nombre, tope=400):
    """Cava un canal descubierto y mete lo bueno en la base.

    No se puede listar un canal por su NOMBRE: hay que llegar a su URL. Por
    eso al descubrirlo se guarda un video suyo — yt-dlp resuelve el canal
    desde cualquier video.
    """
    con = sqlite3.connect(DB)
    con.executescript(ESQUEMA)
    fila = con.execute("""SELECT canal, ejemplo FROM canal_descubierto
                          WHERE canal LIKE ? LIMIT 1""", ("%" + nombre + "%",)).fetchone()
    if not fila or not fila[1]:
        print("no tengo un video de ese canal. Corre primero:  crate diggers")
        con.close()
        return 1
    canal, vid = fila
    print("resolviendo el canal de %s..." % canal)
    r = srv.subprocess.run(
        [srv.YT, "--no-warnings", "-q", "--print", "%(channel_url)s",
         "https://www.youtube.com/watch?v=" + vid],
        capture_output=True, text=True, timeout=90, **srv.SIN_VENTANA)
    url = (r.stdout or "").strip().splitlines()
    if not url:
        print("no pude: %s" % (r.stderr or "")[:140])
        con.close()
        return 1

    print("listando %s (hasta %d subidas, sin gastar quota)..." % (url[0], tope))
    r = srv.subprocess.run(
        [srv.YT, "--flat-playlist", "--no-warnings", "-q", "--ignore-errors",
         "-I", "1:%d" % tope,
         "--print", "%%(id)s%s%%(title)s%s%%(duration)s%s%%(view_count)s"
         % (srv.SEP, srv.SEP, srv.SEP),
         url[0] + "/videos"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600, **srv.SIN_VENTANA)

    hoy = time.strftime("%Y-%m-%d")
    nuevos = descartados = 0
    for ln in (r.stdout or "").splitlines():
        c = ln.split(srv.SEP)
        if len(c) < 4 or len(c[0]) != 11:
            continue
        vid_, tit = c[0], c[1]
        dur = int(c[2]) if c[2].isdigit() else None
        views = int(c[3]) if c[3].isdigit() else None
        if criterios.descartar(tit, dur, views, canal):
            descartados += 1
            continue
        art, nom = srv.partir(tit)
        cur = con.execute("""INSERT OR IGNORE INTO tema(id,titulo,artista,nombre,
                                         canal,duracion,views,agregado)
                             VALUES(?,?,?,?,?,?,?,?)""",
                          (vid_, tit, art, nom, canal, dur, views, hoy))
        if cur.rowcount:
            nuevos += 1
            con.execute("INSERT OR IGNORE INTO origen(id,fuente) VALUES(?,'digger')",
                        (vid_,))
    con.execute("UPDATE canal_descubierto SET cavado=? WHERE canal=?", (hoy, canal))
    con.commit()
    total = con.execute("SELECT count(*) FROM tema WHERE canal=?", (canal,)).fetchone()[0]
    con.close()
    print()
    print("  temas nuevos en la base : %d" % nuevos)
    print("  descartados por filtros : %d" % descartados)
    print("  total de ese canal      : %d" % total)
    print()
    print("ahora:  crate hotlist   para que entren a la cola")
    return 0


def main():
    con = sqlite3.connect(DB)
    con.executescript(ESQUEMA)
    # CREATE TABLE IF NOT EXISTS no agrega columnas a una tabla que ya existe:
    # hay que migrarla a mano. Paso lo mismo con hotlist.genero.
    cols = [r[1] for r in con.execute("PRAGMA table_info(canal_descubierto)")]
    if "ejemplo" not in cols:
        con.execute("ALTER TABLE canal_descubierto ADD COLUMN ejemplo TEXT")
    joyas = con.execute("""
        SELECT t.artista, t.nombre, t.canal FROM tema t
        JOIN marca m ON m.id = t.id
        WHERE m.estrellas >= 4
          AND t.artista IS NOT NULL AND t.nombre IS NOT NULL
        ORDER BY m.estrellas DESC, random() LIMIT ?""", (N,)).fetchall()
    if not joyas:
        print("todavia no puntuaste nada con 4 o 5 estrellas")
        return 1

    print("buscando quien mas subio tus %d mejores temas..." % len(joyas))
    print("(cada busqueda tarda unos segundos; sin gastar quota)")
    print()

    def buscar(j):
        art, nom, _ = j
        try:
            return j, srv.ytsearch("%s %s" % (art, nom), n=10)
        except Exception:
            return j, []

    cuenta, ejemplos, muestra, hechas = {}, {}, {}, 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=4) as ex:
        for (art, nom, mio), res in ex.map(buscar, joyas):
            hechas += 1
            vistos_en_esta = set()
            print("  %3d/%d  %-44s" % (hechas, len(joyas),
                                       ("%s - %s" % (art, nom))[:44]), end="\r")
            for x in res:
                c = x["canal"]
                if not util(c) or c == mio or c in vistos_en_esta:
                    continue
                vistos_en_esta.add(c)
                cuenta[c] = cuenta.get(c, 0) + 1
                ejemplos.setdefault(c, []).append(nom)
                # guardar un video suyo: sin esto no hay forma de llegar al
                # canal despues (yt-dlp resuelve el canal desde un video)
                muestra.setdefault(c, x["id"])

    print(" " * 70, end="\r")
    print("listo en %d s. Canales distintos vistos: %d" % (time.time() - t0, len(cuenta)))
    print()

    # un canal con UNA joya es casualidad; con tres o mas esta cavando lo mismo
    fuertes = sorted(((n, c) for c, n in cuenta.items() if n >= 2), reverse=True)
    if not fuertes:
        print("ninguno repite todavia. Con mas temas puntuados la señal mejora.")
    else:
        print("DIGGERS NUEVOS (tienen varias de tus joyas):")
        print()
        for n, c in fuertes[:15]:
            print("   %-44s %2d joyas" % (c[:44], n))
            print("      p.ej. %s" % ", ".join(ejemplos[c][:2])[:60])

    if GUARDAR and fuertes:
        hoy = time.strftime("%Y-%m-%d")
        for n, c in fuertes:
            con.execute("""INSERT INTO canal_descubierto(canal,joyas,ejemplo,visto)
                           VALUES(?,?,?,?)
                           ON CONFLICT(canal) DO UPDATE SET joyas=excluded.joyas,
                                                            ejemplo=excluded.ejemplo,
                                                            visto=excluded.visto""",
                        (c, n, muestra.get(c), hoy))
        con.commit()
        print()
        print("guardados %d en canal_descubierto. Para cavarlos:" % len(fuertes))
        print("   crate cavar-canal \"<nombre>\"")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
