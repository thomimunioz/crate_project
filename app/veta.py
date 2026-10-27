# -*- coding: utf-8 -*-
"""Mina el pool que YA esta en la base para las vetas flacas (PIANO, DARK, FOLK).

Por que mirar adentro antes de salir a cavar: al 27-oct hay 50.365 temas en
crate.db que nunca se tocaron. Salir a YouTube a buscar "rare piano 70s" cuando
tenes cincuenta mil sin escuchar es cavar al lado del pozo que ya cavaste.

Lo que entra NO va directo a la playlist: va al hotlist, que es la cola de
escucha. Thomas lo oye, lo puntua y lo clasifica. La maquina propone y nada mas.

Senales que usa, en orden de confianza:
  1. tonalidad menor medida por el DSP (dato duro, solo sirve para DARK)
  2. palabras del titulo (lo unico que hay para la enorme mayoria)
  3. el canal, cuando es un curador de genero conocido
y encima de eso, todo lo de criterios.py: basura, 6/8, mainstream, duracion.

Uso:
    python veta.py                   las tres vetas, 25 cada una
    python veta.py PIANO --n=40      una sola
    python veta.py --ver             muestra que haria, no guarda
"""
import json
import os
import re
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import criterios

DB = r"G:\Thomi - Mi Carpeta\crate_project\crate.db"
B = chr(92) + "b"          # nunca escribir el borde de palabra a mano: ver NOTA
VER = "--ver" in sys.argv
CUPO = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--n=")), "25"))

# NOTA (27-oct): este archivo se escribio una vez por heredoc y los "\b" de las
# regex llegaron convertidos en el caracter de retroceso. Cincuenta filtros
# quedaron matcheando nada, en silencio, porque ese caracter no se imprime.
# Por eso el borde de palabra se construye, no se tipea.


def rx(*trozos):
    """Una alternativa de palabras completas, inmune al bug del heredoc."""
    return re.compile(B + "(?:" + "|".join(trozos) + ")" + B, re.I)


# Canales de covers, versiones MIDI y musica funcional: el titulo dice "piano"
# pero no es un disco de nadie. Se cuelan justo por la palabra que buscamos.
SOSPECHOSO = rx("love songs", "backing track", "relaxing", "study music",
                "sleep music", "meditation", "easy listening piano",
                "synthesia", "midi", "cover version", "played by",
                "greatest hits", "best of", "top 10", "top 20")


VETAS = {
    "PIANO": {
        "si": rx("piano", "rhodes", "wurlitzer", "wurli", "clavinet", "harpsichord",
                 "keyboards?", "fender rhodes", "electric piano", "keys",
                 "pianist", "klavier", "pianoforte"),
        "muy": rx("solo piano", "piano solo", "rhodes", "electric piano",
                  "piano instrumental", "wurlitzer"),
        "no": rx("piano bar", "piano cover", "tutorial", "lesson", "karaoke"),
    },
    "DARK": {
        "si": rx("dark", "darkness", "melancholy", "melancholic", "melancholia",
                 "sombre", "somber", "moody", "lament", "sorrow", "mourning",
                 "shadow", "shadows", "noir", "requiem", "elegy", "haunting",
                 "haunted", "eerie", "sinister", "dusk", "midnight", "despair",
                 "lonely", "loneliness", "grief", "funeral", "tristeza",
                 "melancolia", "oscuro", "sombra", "nocturne"),
        "muy": rx("dark", "melancholic", "noir", "requiem", "haunting", "nocturne"),
        "no": rx("dark side of the moon", "darkchild"),
    },
    "FOLK": {
        "si": rx("folk", "acoustic", "acustico", "violao", "troubadour",
                 "singer.?songwriter", "loner", "psych folk", "acid folk",
                 "fingerstyle", "fingerpicking", "ballad", "balada", "guitar",
                 "guitarra", "banjo", "mandolin", "dulcimer", "pastoral"),
        "muy": rx("folk", "acid folk", "psych folk", "loner", "acoustic",
                  "fingerstyle", "private press"),
        "no": rx("folk dance", "folklore festival", "rock n roll"),
    },
}


SEPARADOR = re.compile(r"\s(?:[-–—/|:]|‎-)\s")


def parte_tema(titulo):
    """El titulo sin el artista.

    Hace falta porque "Rhodes" es tambien un apellido: Cynthia Rhodes no toca
    un Fender Rhodes, canta. Las pistas de instrumento solo valen si estan del
    lado del TEMA, no del lado de quien firma. Las etiquetas de genero que
    ponen los canales digger ([US] Jazz, Folk) tambien caen de este lado.
    """
    t = titulo or ""
    partes = SEPARADOR.split(t, 1)
    return partes[1] if len(partes) > 1 else t


def senal(titulo, canal, menor, bpm, veta):
    """Cuanta evidencia hay de que el tema pertenece a la veta."""
    v = VETAS[veta]
    entero = titulo or ""
    t = parte_tema(entero)
    if v["no"].search(entero) or SOSPECHOSO.search(entero):
        return 0.0, []
    razones = []
    s = 0.0
    if v["muy"].search(t):
        s += 2.0
        razones.append("el titulo lo dice")
    elif v["si"].search(t):
        s += 1.0
        razones.append("pista en el titulo")
    if veta == "DARK" and menor:
        # La tonalidad menor SOLA no alcanza: media discografia soul esta en
        # menor y no tiene nada de oscura. Vale cuando ademas el tema es lento
        # o no tiene voz, que es cuando de verdad suena sombrio y sampleable.
        hueco = criterios.SIN_VOZ.search(t) or (bpm and bpm <= 95)
        s += 1.2 if hueco else 0.8
        razones.append("menor y lento" if hueco else "tonalidad menor medida")
    if veta == "PIANO" and criterios.PIANO.search(t):
        s += 0.4
    return s, razones


def minar(con, veta, cupo):
    filas = con.execute("""
      SELECT t.id, t.titulo, t.canal, t.duracion, t.views, t.anio,
             a.bpm_real, a.menor
      FROM tema t
      LEFT JOIN analisis a ON a.id = t.id
      WHERE t.oculto = 0
        AND t.duracion BETWEEN 165 AND 900
        AND NOT EXISTS (SELECT 1 FROM marca      m WHERE m.id = t.id)
        AND NOT EXISTS (SELECT 1 FROM en_playlist p WHERE p.id = t.id)
        AND NOT EXISTS (SELECT 1 FROM hotlist    h WHERE h.id = t.id)
    """).fetchall()

    pasan = []
    for r in filas:
        if criterios.descartar(r["titulo"], r["duracion"], r["views"], r["canal"]):
            continue
        sen, raz_v = senal(r["titulo"], r["canal"], r["menor"], r["bpm_real"], veta)
        if sen < 1.0:                      # sin evidencia no entra: no adivinamos
            continue
        pts, raz = criterios.puntuar(r["titulo"], r["duracion"], r["views"],
                                     r["canal"], r["anio"], r["bpm_real"], r["menor"])
        pasan.append((pts + sen, ["veta " + veta] + raz_v + raz, dict(r)))

    pasan.sort(key=lambda x: -x[0])

    elegidos, por_canal, por_art = [], {}, {}
    for pts, raz, r in pasan:
        c = r["canal"] or "?"
        a = criterios.quitar_tildes((r["titulo"] or "").split(" - ")[0])[:22]
        if por_canal.get(c, 0) >= 4 or por_art.get(a, 0) >= 2:
            continue
        por_canal[c] = por_canal.get(c, 0) + 1
        por_art[a] = por_art.get(a, 0) + 1
        elegidos.append((pts, raz, r))
        if len(elegidos) >= cupo:
            break
    return len(pasan), elegidos


def main():
    pedidas = [a for a in sys.argv[1:] if a.upper() in VETAS]
    vetas = [a.upper() for a in pedidas] or list(VETAS)

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS hotlist(
                     id TEXT PRIMARY KEY REFERENCES tema(id) ON DELETE CASCADE,
                     pts REAL, razones TEXT, tanda TEXT, agregado TEXT)""")
    hoy = time.strftime("%Y-%m-%d")

    total = 0
    for veta in vetas:
        tengo = con.execute("SELECT count(*) FROM en_playlist WHERE playlist=?",
                            (veta,)).fetchone()[0]
        n, elegidos = minar(con, veta, CUPO)
        print("%-6s  tenes %3d en la lista  |  candidatos %5d  ->  entran %2d"
              % (veta, tengo, n, len(elegidos)))
        for pts, raz, r in elegidos[:6]:
            print("        %+5.1f  %-58s" % (pts, (r["titulo"] or "")[:58]))
            print("               %s" % " · ".join(raz[:3])[:70])
        if not VER:
            for pts, raz, r in elegidos:
                con.execute("""INSERT OR REPLACE INTO
                               hotlist(id, pts, razones, tanda, agregado)
                               VALUES(?,?,?,?,?)""",
                            (r["id"], pts, json.dumps(raz, ensure_ascii=False),
                             "veta-" + veta.lower(), hoy))
        total += len(elegidos)
        print()

    if VER:
        print("(--ver: no guarde nada)")
    else:
        con.commit()
        vivos = con.execute("SELECT count(*) FROM hot").fetchone()[0]
        print("sumados al hotlist: %d  ->  %d esperandote" % (total, vivos))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
