# -*- coding: utf-8 -*-
"""HOTLIST: los mejores candidatos que todavia no escuchaste, siempre frescos.

Es el proceso de la demo, automatizado. Thomas, 27-oct: "que haya un endpoint
que sea corte un hotlist de 50 temas que vos buscas (...) y eso se actualiza y/o
stackea semanalmente (hasta un cierto tope) y se va limpiando a medida que yo
voy escuchando y votando, ahi ya salen de ese top".

Como funciona:
  * cada corrida mete hasta NUEVOS_POR_TANDA candidatos
  * nunca pasa de TOPE temas vivos: si no escuchaste, no se acumula infinito
  * los que puntuas, rechazas o abris salen SOLOS (la vista los filtra por marca)
  * lo que entra sale del pool cavado, pasado por criterios.py y ordenado por lo
    que historicamente rinde (canal, espacio instrumental, duracion, tempo)

Uso:
    python hotlist.py            genera la tanda de esta semana
    python hotlist.py --ver      muestra que haria
    python hotlist.py --medir    ademas mide BPM/tonalidad de los nuevos (lento)
"""
import json, os, sqlite3, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import criterios

DB = r"G:\Thomi - Mi Carpeta\crate_project\crate.db"
TOPE = 150                 # maximo de temas vivos en el hotlist
NUEVOS_POR_TANDA = 50
VER = "--ver" in sys.argv
MEDIR = "--medir" in sys.argv

ESQUEMA = """
CREATE TABLE IF NOT EXISTS hotlist(
  id       TEXT PRIMARY KEY REFERENCES tema(id) ON DELETE CASCADE,
  pts      REAL,
  razones  TEXT,
  tanda    TEXT,          -- la semana en que entro
  agregado TEXT
);
CREATE INDEX IF NOT EXISTS ix_hot_pts ON hotlist(pts DESC);

-- lo que sigue vivo: lo que todavia no tocaste
CREATE VIEW IF NOT EXISTS hot AS
SELECT h.id, h.pts, h.razones, h.tanda,
       t.titulo, t.artista, t.nombre, t.canal, t.anio, t.duracion, t.views,
       a.bpm_real AS bpm, a.tonalidad, a.menor,
       'https://www.youtube.com/watch?v=' || t.id AS url
FROM hotlist h
JOIN tema t ON t.id = h.id
LEFT JOIN analisis a ON a.id = h.id
WHERE t.oculto = 0
  AND NOT EXISTS (SELECT 1 FROM marca m WHERE m.id = h.id)
ORDER BY h.pts DESC;
"""


def generar():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    cur = con.cursor()
    hoy = time.strftime("%Y-%m-%d")
    semana = time.strftime("%Y-S%V")

    vivos = cur.execute("SELECT count(*) FROM hot").fetchone()[0]
    print("hotlist: %d vivos (tope %d)" % (vivos, TOPE))
    # limpieza: lo que ya tocaste no tiene por que seguir ocupando lugar
    muertos = cur.execute("""DELETE FROM hotlist WHERE id IN
        (SELECT h.id FROM hotlist h JOIN marca m ON m.id=h.id)""").rowcount
    if muertos:
        print("  saco %d que ya escuchaste o puntuaste" % muertos)

    cupo = min(NUEVOS_POR_TANDA, TOPE - vivos)
    if cupo <= 0:
        print("  el hotlist esta lleno, no agrego hasta que escuches")
        con.commit(); con.close()
        return 0

    # --- candidatos: lo que esta en la base, nunca marcado, nunca en hotlist ---
    filas = cur.execute("""
      SELECT t.id, t.titulo, t.canal, t.duracion, t.views, t.anio,
             a.bpm_real, a.menor
      FROM tema t
      LEFT JOIN analisis a ON a.id = t.id
      WHERE t.oculto = 0
        AND t.duracion BETWEEN 165 AND 900
        AND NOT EXISTS (SELECT 1 FROM marca m WHERE m.id = t.id)
        AND NOT EXISTS (SELECT 1 FROM hotlist h WHERE h.id = t.id)
        AND NOT EXISTS (SELECT 1 FROM en_playlist p WHERE p.id = t.id)
    """).fetchall()
    print("  candidatos en la base: %d" % len(filas))

    pasan, desc = [], {}
    for r in filas:
        motivo = criterios.descartar(r["titulo"], r["duracion"], r["views"], r["canal"])
        if motivo:
            desc[motivo] = desc.get(motivo, 0) + 1
            continue
        pts, raz = criterios.puntuar(r["titulo"], r["duracion"], r["views"],
                                     r["canal"], r["anio"], r["bpm_real"], r["menor"])
        pasan.append((pts, raz, dict(r)))
    print("  pasan los filtros: %d" % len(pasan))
    for k, v in sorted(desc.items(), key=lambda kv: -kv[1])[:5]:
        print("     %-44s %d" % (k[:44], v))

    pasan.sort(key=lambda x: -x[0])

    # variedad: que no entren 20 del mismo canal ni del mismo artista
    elegidos, por_canal, por_art = [], {}, {}
    for pts, raz, r in pasan:
        c = r["canal"] or "?"
        a = criterios.quitar_tildes((r["titulo"] or "").split(" - ")[0])[:22]
        if por_canal.get(c, 0) >= max(3, cupo // 6):
            continue
        if por_art.get(a, 0) >= 2:
            continue
        por_canal[c] = por_canal.get(c, 0) + 1
        por_art[a] = por_art.get(a, 0) + 1
        elegidos.append((pts, raz, r))
        if len(elegidos) >= cupo:
            break

    print("\n  entran %d (tanda %s)" % (len(elegidos), semana))
    for pts, raz, r in elegidos[:10]:
        print("     %+5.1f  %-52s" % (pts, (r["titulo"] or "")[:52]))
        if raz:
            print("            %s" % " · ".join(raz[:2])[:62])

    if VER:
        print("\n(--ver: no guarde nada)")
        con.close()
        return 0

    for pts, raz, r in elegidos:
        cur.execute("""INSERT OR REPLACE INTO hotlist(id,pts,razones,tanda,agregado)
                       VALUES(?,?,?,?,?)""",
                    (r["id"], pts, json.dumps(raz, ensure_ascii=False), semana, hoy))
    con.commit()
    total = cur.execute("SELECT count(*) FROM hot").fetchone()[0]
    print("\n  hotlist ahora: %d vivos" % total)

    if MEDIR:
        faltan = [r[0] for r in cur.execute(
            "SELECT id FROM hot WHERE bpm IS NULL LIMIT 40")]
        if faltan:
            print("\n  midiendo %d con el DSP…" % len(faltan))
            subprocess.run([sys.executable, os.path.join(HERE, "bpm.py")] + faltan,
                           capture_output=True)
            print("  medidos. Corre bd_build.py para volcarlos a la base.")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(generar())
