# -*- coding: utf-8 -*-
"""Arma crate.db: la base de datos propia de Thomas.

El problema que resuelve (sus palabras, 27-oct): "por si pierdo la cuenta, se
ocultan videos, o lo que sea". Las playlists de YouTube son prestadas — 4 de sus
662 temas ya estan borrados o en privado, y sin esto no quedaria ni el titulo.

Guarda TODO lo que sabemos de cada tema, de modo que si el video muere el tema
sigue siendo identificable y rastreable (por ejemplo en Soulseek).
"""
import json, os, re, sqlite3, glob, unicodedata, time
HERE = os.path.dirname(os.path.abspath(__file__))
DB = r"G:\Thomi - Mi Carpeta\crate_project\crate.db"

ESQUEMA = """
PRAGMA journal_mode=WAL;

-- el tema en si, exista o no el video
CREATE TABLE IF NOT EXISTS tema (
  id          TEXT PRIMARY KEY,         -- id de YouTube (11 chars)
  titulo      TEXT NOT NULL,            -- titulo crudo, como vino
  artista     TEXT,                     -- parseado del titulo
  nombre      TEXT,                     -- parseado del titulo
  canal       TEXT,                     -- quien lo subio
  duracion    INTEGER,                  -- segundos
  views       INTEGER,
  anio        INTEGER,
  anio_fuente TEXT,                     -- phonogram | titulo | descripcion
  vivo        INTEGER DEFAULT 1,        -- 0 = borrado o privado
  agregado    TEXT                      -- cuando entro a la base
);
CREATE INDEX IF NOT EXISTS ix_tema_artista ON tema(artista);
CREATE INDEX IF NOT EXISTS ix_tema_anio    ON tema(anio);
CREATE INDEX IF NOT EXISTS ix_tema_canal   ON tema(canal);

-- lo que midio el DSP sobre el audio real
CREATE TABLE IF NOT EXISTS analisis (
  id        TEXT PRIMARY KEY REFERENCES tema(id) ON DELETE CASCADE,
  bpm       REAL,                       -- lo que leyo el analizador
  bpm_real  REAL,                       -- plegado a la octava que el usa
  bpm_conf  REAL,
  tonalidad TEXT,
  key_conf  REAL,
  menor     INTEGER,                    -- 1 si es menor
  medido    TEXT
);
CREATE INDEX IF NOT EXISTS ix_analisis_bpm ON analisis(bpm_real);

-- lo que Thomas decidio sobre cada tema
CREATE TABLE IF NOT EXISTS marca (
  id        TEXT REFERENCES tema(id) ON DELETE CASCADE,
  estado    TEXT,                       -- guardado | rechazado | visto
  estrellas INTEGER,                    -- 1-5, solo si lo guardo
  motivo    TEXT,                       -- por que no
  nota      TEXT,
  tanda     TEXT,                       -- de que lista salio
  fecha     TEXT,
  PRIMARY KEY (id, tanda)
);
CREATE INDEX IF NOT EXISTS ix_marca_estado ON marca(estado);

-- en cuales de sus 5 playlists esta
CREATE TABLE IF NOT EXISTS en_playlist (
  id       TEXT REFERENCES tema(id) ON DELETE CASCADE,
  playlist TEXT,
  PRIMARY KEY (id, playlist)
);

-- de donde salio como candidato
CREATE TABLE IF NOT EXISTS origen (
  id     TEXT REFERENCES tema(id) ON DELETE CASCADE,
  fuente TEXT,
  PRIMARY KEY (id, fuente)
);

-- el archivo en el disco. La base es el MAPA: dice que bajar y donde quedo.
CREATE TABLE IF NOT EXISTS archivo (
  id       TEXT REFERENCES tema(id) ON DELETE CASCADE,
  ruta     TEXT,                      -- donde esta en el disco duro
  formato  TEXT,                      -- flac | mp3 | wav
  bitrate  INTEGER,                   -- kbps (null en flac)
  bytes    INTEGER,
  fuente   TEXT,                      -- soulseek | youtube | propio
  bajado   TEXT,
  PRIMARY KEY (id, ruta)
);
CREATE INDEX IF NOT EXISTS ix_archivo_id ON archivo(id);

-- LA LISTA DE COMPRAS: lo que vale la pena y todavia no esta en el disco.
-- Ordenado por estrellas: primero lo que puntuo 5.
CREATE VIEW IF NOT EXISTS por_bajar AS
SELECT t.id, t.artista, t.nombre, t.titulo, t.anio,
       a.bpm_real AS bpm, a.tonalidad,
       (SELECT max(m.estrellas) FROM marca m WHERE m.id=t.id) AS estrellas,
       (SELECT group_concat(p.playlist,' + ') FROM en_playlist p WHERE p.id=t.id) AS playlists,
       t.vivo,
       'https://www.youtube.com/watch?v=' || t.id AS url
FROM tema t
LEFT JOIN analisis a ON a.id=t.id
WHERE NOT EXISTS (SELECT 1 FROM archivo f WHERE f.id=t.id)
  AND ( EXISTS (SELECT 1 FROM en_playlist p WHERE p.id=t.id)
     OR EXISTS (SELECT 1 FROM marca m WHERE m.id=t.id AND m.estado='guardado') )
ORDER BY estrellas DESC NULLS LAST, t.anio;

-- lo que ya esta en el disco
CREATE VIEW IF NOT EXISTS biblioteca AS
SELECT t.id, t.artista, t.nombre, t.anio, a.bpm_real AS bpm, a.tonalidad,
       f.ruta, f.formato, f.bitrate, round(f.bytes/1048576.0,1) AS mb, f.fuente
FROM archivo f JOIN tema t ON t.id=f.id LEFT JOIN analisis a ON a.id=t.id;

-- vista unica: todo junto, una fila por tema
CREATE VIEW IF NOT EXISTS crate AS
SELECT t.id, t.titulo, t.artista, t.nombre, t.canal, t.anio,
       t.duracion, t.views, t.vivo,
       a.bpm_real AS bpm, a.tonalidad, a.menor,
       (SELECT group_concat(p.playlist, ' + ') FROM en_playlist p WHERE p.id=t.id) AS playlists,
       (SELECT m.estado    FROM marca m WHERE m.id=t.id ORDER BY m.fecha DESC LIMIT 1) AS estado,
       (SELECT m.estrellas FROM marca m WHERE m.id=t.id AND m.estrellas>0 ORDER BY m.fecha DESC LIMIT 1) AS estrellas,
       (SELECT m.motivo    FROM marca m WHERE m.id=t.id AND m.motivo<>'' ORDER BY m.fecha DESC LIMIT 1) AS motivo,
       'https://www.youtube.com/watch?v=' || t.id AS url
FROM tema t LEFT JOIN analisis a ON a.id=t.id;
"""

RUIDO_T = re.compile(
    r"\(([^)]*)\)|\[([^\]]*)\]|\b(official|audio|video|hq|hd|4k|vinyl|rip|lyrics?|"
    r"visualizer|remaster\w*|full|version|unreleased|rare|obscure|soul sample|"
    r"samples?)\b", re.I)

def partir(t):
    """Separa 'Artista - Tema' limpiando el ruido tipico de YouTube."""
    s = RUIDO_T.sub(" ", t)
    s = re.sub(r"\b(19|20)\d{2}\b", " ", s)
    s = re.sub(r"[\u266a\u2022|#]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" -\u2013\u2014:.,")
    m = re.split(r"\s+[-\u2013\u2014]\s+|\s*:\s+", s, 1)
    if len(m) == 2 and 1 < len(m[0]) < 60 and len(m[1]) > 1:
        return m[0].strip(), m[1].strip()
    return None, s or None

def plegar(b):
    return b / 2 if b and b > 115 and 55 <= b / 2 <= 115 else b

MUERTO = re.compile(r"\[deleted video\]|\[private video\]|video no disponible", re.I)
HOY = time.strftime("%Y-%m-%d")

con = sqlite3.connect(DB)
con.executescript(ESQUEMA)
cur = con.cursor()

# ---------- temas ----------
meta = json.load(open(os.path.join(HERE, "meta_cache.json"), encoding="utf-8"))
bpmc = json.load(open(os.path.join(HERE, "bpm_cache.json"), encoding="utf-8"))

fuentes = {
 "playlist": "pl_pool.json", "krem": "krem_nuevo.json",
 "cavado": "demo_cavado.json", "five-special": "fsr_nuevo.json",
 "library-este": "ws_pool.json", "curadores": "vetas_pool.json",
 "latam": "latam_pool.json",
}
vistos = {}
for fuente, f in fuentes.items():
    p = os.path.join(HERE, f)
    if not os.path.exists(p):
        continue
    d = json.load(open(p, encoding="utf-8"))
    # unos json son {id: {...}} y otros [{id:..., ...}]
    pares = d.items() if isinstance(d, dict) else ((x.get("id"), x) for x in d)
    for vid, e in pares:
        if not vid or len(vid) != 11:
            continue
        vistos.setdefault(vid, e)
        cur.execute("INSERT OR IGNORE INTO origen(id,fuente) VALUES(?,?)", (vid, fuente))

for vid, e in vistos.items():
    m = meta.get(vid, {})
    tit = (m.get("title") or e.get("title") or "").strip()
    art, nom = partir(tit)
    anio = m.get("year")
    anio = int(anio) if str(anio or "").isdigit() else None
    cur.execute("""INSERT INTO tema(id,titulo,artista,nombre,canal,duracion,views,anio,anio_fuente,vivo,agregado)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     titulo=excluded.titulo, artista=excluded.artista, nombre=excluded.nombre,
                     canal=COALESCE(excluded.canal,tema.canal),
                     views=COALESCE(excluded.views,tema.views),
                     anio=COALESCE(excluded.anio,tema.anio), vivo=excluded.vivo""",
                (vid, tit, art, nom,
                 (m.get("uploader") or e.get("uploader") or "").replace(" - Topic", "").strip() or None,
                 e.get("dur"), m.get("views") if m.get("views") is not None else e.get("views"),
                 anio, m.get("year_src"), 0 if MUERTO.search(tit) else 1, HOY))

# ---------- analisis ----------
for vid, b in bpmc.items():
    if not b.get("bpm") or vid not in vistos:
        continue
    k = b.get("key") or ""
    cur.execute("""INSERT OR REPLACE INTO analisis
                   (id,bpm,bpm_real,bpm_conf,tonalidad,key_conf,menor,medido)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (vid, b["bpm"], round(plegar(b["bpm"]), 1), b.get("bpm_conf"),
                 k or None, b.get("key_conf"), 1 if "minor" in k else 0, HOY))

# ---------- playlists ----------
pl = json.load(open(os.path.join(HERE, "pl_pool.json"), encoding="utf-8"))
NOM = {"80s": "80s", "soul": "SOUL", "rnb": "R&B SOUL",
       "citypop": "CITY POP", "fusion": "JAZZ FUSION",
       "piano": "PIANO", "dark": "DARK", "folk": "FOLK"}
for vid, e in pl.items():
    for L in e.get("listas", []):
        cur.execute("INSERT OR IGNORE INTO en_playlist(id,playlist) VALUES(?,?)",
                    (vid, NOM.get(L, L)))

# ---------- marcas ----------
for f in sorted(glob.glob(r"C:\Users\thomi\Downloads\crate-feedback-*.json"),
                key=os.path.getmtime):
    d = json.load(open(f, encoding="utf-8"))
    tanda = d.get("pagina", os.path.basename(f))[:60]
    fecha = (d.get("fecha") or "")[:10] or HOY
    for t in d["temas"]:
        vid = t["id"]
        if vid not in vistos:        # un tema marcado que no esta en ningun pool
            art, nom = partir(t["titulo"])
            cur.execute("INSERT OR IGNORE INTO tema(id,titulo,artista,nombre,agregado) VALUES(?,?,?,?,?)",
                        (vid, t["titulo"], art, nom, HOY))
            vistos[vid] = {}
        estado = ("guardado" if t.get("agregado")
                  else "rechazado" if t.get("motivo")
                  else "visto" if t.get("abierto") else None)
        if not estado:
            continue
        cur.execute("""INSERT OR REPLACE INTO marca(id,estado,estrellas,motivo,nota,tanda,fecha)
                       VALUES(?,?,?,?,?,?,?)""",
                    (vid, estado, t.get("estrellas") or None, t.get("motivo") or None,
                     t.get("nota") or None, tanda, fecha))

con.commit()
q = lambda s: cur.execute(s).fetchone()[0]
print("crate.db -> %s" % DB)
print("  temas        %6d  (%d con el video caido)" % (q("SELECT count(*) FROM tema"),
                                                       q("SELECT count(*) FROM tema WHERE vivo=0")))
print("  analisis     %6d" % q("SELECT count(*) FROM analisis"))
print("  marcas       %6d  (%d guardados, %d con estrellas)" % (
    q("SELECT count(*) FROM marca"),
    q("SELECT count(*) FROM marca WHERE estado='guardado'"),
    q("SELECT count(*) FROM marca WHERE estrellas>0")))
print("  en playlists %6d" % q("SELECT count(DISTINCT id) FROM en_playlist"))
print("  tamaño       %6.1f MB" % (os.path.getsize(DB) / 1e6))
con.close()
