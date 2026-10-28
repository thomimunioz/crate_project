# -*- coding: utf-8 -*-
"""HOTLIST: la crema de la semana, en los generos que Thomas ya trabaja.

Thomas, 28-oct-2026: "semanalmente eso tiene que ser lo mejor de lo mejor, en
los generos q estuvimos ya trabajando (...) en hotlist siempre tiene que estar
la verdadera crema. Acepto obviamente recomendaciones de piano dark y folk,
pero lo que venimos trabajando es el fuerte."

De ahi salen dos reglas. La tercera viene de medir: ninguna señal de metadata
predice su gusto (AUC 0.43-0.57 sobre 195 marcas). La unica que predice es
QUIEN lo subio. Asi que el canal medido pesa mas que todo lo demas junto, y lo
que viene de un canal sin medir entra con recelo.

  * tres cuartos de la tanda son generos fuertes, un cuarto en formacion
  * ningun genero se come mas de un tercio
  * nunca pasa de TOPE temas vivos: si no escuchas, no se acumula infinito
  * los que puntuas o rechazas salen SOLOS (la vista los filtra por marca)

Que cambio el 28-oct (antes esto traia "medio medio", y con razon):
62 de 120 temas venian de canales nunca medidos, solo 18 de 120 tenian año, y
las razones que mas se repetian —tonalidad menor, palabras del titulo— son
justamente las que NO predicen nada.

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
REHACER = "--rehacer" in sys.argv

CUPO_FORMACION = 0.25      # PIANO, DARK, FOLK: recomendacion, no relleno
POR_GENERO = 0.35          # que ningun genero se coma mas de un tercio

ESQUEMA = """
CREATE TABLE IF NOT EXISTS hotlist(
  id       TEXT PRIMARY KEY REFERENCES tema(id) ON DELETE CASCADE,
  pts      REAL,
  razones  TEXT,
  tanda    TEXT,          -- la semana en que entro
  agregado TEXT
);
CREATE INDEX IF NOT EXISTS ix_hot_pts ON hotlist(pts DESC);
"""

# La columna de genero y la vista se crean aparte porque la tabla ya existia
# sin ellas: un CREATE TABLE IF NOT EXISTS no agrega columnas a una tabla vieja.
VISTA = """
DROP VIEW IF EXISTS hot;
CREATE VIEW hot AS
SELECT h.id, h.pts, h.razones, h.genero, h.tanda,
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


def preparar(con):
    con.executescript(ESQUEMA)
    cols = [r[1] for r in con.execute("PRAGMA table_info(hotlist)")]
    if "genero" not in cols:
        con.execute("ALTER TABLE hotlist ADD COLUMN genero TEXT")
    con.executescript(VISTA)


def peso_canal(canal):
    """Lo que de verdad predice.

    Devuelve 0 si el canal nunca se midio. No es un castigo: es no tener con
    que opinar, y para la crema semanal preferimos lo que sabemos. Los que
    quedan afuera se van midiendo solos a medida que Thomas puntua.
    """
    hr = criterios.CANALES.get(canal)
    if hr is None:
        return 0.0, None
    return (hr - criterios.BASE) * 6.0, hr


def generar():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    preparar(con)
    cur = con.cursor()
    hoy = time.strftime("%Y-%m-%d")
    semana = time.strftime("%Y-S%V")

    if REHACER:
        # saca las sugerencias que todavia no escuchaste. No se pierde nada:
        # los temas siguen en la base y lo que ya puntuaste vive en `marca`.
        n = cur.execute("""DELETE FROM hotlist WHERE id NOT IN
                           (SELECT id FROM marca)""").rowcount
        con.commit()
        print("rehaciendo: saque %d sugerencias sin escuchar" % n)

    vivos = cur.execute("SELECT count(*) FROM hot").fetchone()[0]
    print("hotlist: %d vivos (tope %d)" % (vivos, TOPE))
    muertos = cur.execute("""DELETE FROM hotlist WHERE id IN
        (SELECT h.id FROM hotlist h JOIN marca m ON m.id=h.id)""").rowcount
    if muertos:
        print("  saco %d que ya escuchaste o puntuaste" % muertos)

    cupo = min(NUEVOS_POR_TANDA, TOPE - vivos)
    if cupo <= 0:
        print("  el hotlist esta lleno, no agrego hasta que escuches")
        con.commit(); con.close()
        return 0

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
        -- mismo tema subido dos veces con distinto id: si ya tenes un gemelo
        -- en alguna lista, esto no es un descubrimiento
        AND NOT EXISTS (SELECT 1 FROM tema g JOIN en_playlist p ON p.id = g.id
                        WHERE g.titulo = t.titulo AND g.id <> t.id)
    """).fetchall()
    print("  candidatos en la base: %d" % len(filas))

    pasan, desc = [], {}
    for r in filas:
        motivo = criterios.descartar(r["titulo"], r["duracion"], r["views"], r["canal"])
        if motivo:
            desc[motivo] = desc.get(motivo, 0) + 1
            continue
        gen = criterios.genero_de(r["titulo"], r["canal"])
        if gen is None:
            desc["no se de que genero es"] = desc.get("no se de que genero es", 0) + 1
            continue
        pts, raz = criterios.puntuar(r["titulo"], r["duracion"], r["views"],
                                     r["canal"], r["anio"], r["bpm_real"], r["menor"])
        extra, hr = peso_canal(r["canal"])
        pts += extra
        if hr is None:
            raz = raz + ["canal todavia sin medir"]
        pasan.append((pts, raz, gen, dict(r)))

    print("  pasan los filtros: %d" % len(pasan))
    for k, v in sorted(desc.items(), key=lambda kv: -kv[1])[:5]:
        print("     %-44s %d" % (k[:44], v))

    pasan.sort(key=lambda x: -x[0])

    tope_form = max(1, int(cupo * CUPO_FORMACION))
    tope_gen = max(2, int(cupo * POR_GENERO))
    elegidos, por_canal, por_art, por_gen = [], {}, {}, {}

    def tomar(cand, limite):
        """Elige de `cand` hasta llegar a `limite`, cuidando la variedad."""
        for pts, raz, gen, r in cand:
            if len(elegidos) >= limite:
                return
            c = r["canal"] or "?"
            a = criterios.quitar_tildes((r["titulo"] or "").split(" - ")[0])[:22]
            if por_gen.get(gen, 0) >= tope_gen:
                continue
            if por_canal.get(c, 0) >= max(3, cupo // 6) or por_art.get(a, 0) >= 2:
                continue
            por_canal[c] = por_canal.get(c, 0) + 1
            por_art[a] = por_art.get(a, 0) + 1
            por_gen[gen] = por_gen.get(gen, 0) + 1
            elegidos.append((pts, raz, gen, r))

    # Primero los fuertes, que es el grueso. Despues PIANO/DARK/FOLK en su
    # lugar RESERVADO: si fuera solo un techo nunca entrarian, porque los
    # fuertes salen de canales medidos y siempre puntuan mas alto. Thomas los
    # pidio como recomendacion, no como relleno.
    fuertes = [x for x in pasan if x[2] in criterios.FUERTES]
    formacion = [x for x in pasan if x[2] in criterios.EN_FORMACION]
    tomar(fuertes, cupo - tope_form)
    tomar(formacion, len(elegidos) + tope_form)
    tomar(fuertes, cupo)                       # si sobro lugar, mas crema

    print()
    print("  entran %d (tanda %s)" % (len(elegidos), semana))
    print("  por genero: %s" % ", ".join(
        "%s %d" % (g, n) for g, n in sorted(por_gen.items(), key=lambda x: -x[1])))
    medidos = sum(1 for _, _, _, r in elegidos
                  if criterios.CANALES.get(r["canal"]) is not None)
    print("  de canal medido: %d de %d" % (medidos, len(elegidos)))
    print()
    for pts, raz, gen, r in elegidos[:8]:
        print("     %+5.1f  [%-11s] %-44s" % (pts, gen, (r["titulo"] or "")[:44]))
        if raz:
            print("              %s" % " . ".join(raz[:2])[:66])

    if VER:
        print()
        print("(--ver: no guarde nada)")
        con.close()
        return 0

    for pts, raz, gen, r in elegidos:
        cur.execute("""INSERT OR REPLACE INTO
                       hotlist(id,pts,razones,genero,tanda,agregado)
                       VALUES(?,?,?,?,?,?)""",
                    (r["id"], pts, json.dumps(raz, ensure_ascii=False), gen,
                     semana, hoy))
    con.commit()
    total = cur.execute("SELECT count(*) FROM hot").fetchone()[0]
    print()
    print("  hotlist ahora: %d vivos" % total)

    if MEDIR:
        faltan = [r[0] for r in cur.execute(
            "SELECT id FROM hot WHERE bpm IS NULL LIMIT 40")]
        if faltan:
            print("  midiendo %d con el DSP..." % len(faltan))
            # sin timeout, un yt-dlp colgado deja la tanda a medias para
            # siempre. 40 temas a ~4 min de tope cada uno: 45 min alcanza.
            subprocess.run([sys.executable, os.path.join(HERE, "bpm.py")] + faltan,
                           capture_output=True, timeout=2700)
            print("  medidos. Corre bd_build.py para volcarlos a la base.")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(generar())
