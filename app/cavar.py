# -*- coding: utf-8 -*-
"""Sale a YouTube a cavar una veta y deja lo bueno en el hotlist.

Hermano de veta.py: aquel mina lo que YA esta en crate.db, este trae material
nuevo. Se usa cuando el pool interno no da mas (PIANO: 23 candidatos sobre
50.365 temas, o sea que de piano no hay nada guardado).

Cero quota: yt-dlp con ytsearch, igual que el buscador de la app. Lo que entra
pasa por los mismos filtros medidos (criterios.py) mas la senal de la veta
(veta.py), asi que no hay un criterio nuevo que mantener.

Lo cavado entra como tema con origen 'cavado' y va al hotlist para que lo
escuches. Nada se agrega a tus listas: eso lo decidis vos.

Uso:
    python cavar.py PIANO              20 queries, 25 al hotlist
    python cavar.py DARK --n=30
    python cavar.py PIANO --ver        no guarda nada
"""
import json
import os
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import criterios
import crate_server as srv
import veta as mod_veta

DB = r"G:\Thomi - Mi Carpeta\crate_project\crate.db"
VER = "--ver" in sys.argv
CUPO = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--n=")), "25"))

# Queries por veta. No son "piano 70s" a secas: cada una apunta a una forma
# concreta de prensado donde suele haber espacio instrumental, que es la ley de
# oro. Private press, library y lado B rinden mas que cualquier adjetivo.
QUERIES = {
    "PIANO": [
        "rare fender rhodes instrumental 1974 vinyl",
        "electric piano library music instrumental",
        "solo piano private press lp rare",
        "rhodes jazz funk instrumental obscure 45",
        "wurlitzer soul instrumental rare vinyl",
        "piano interlude soul lp 1973",
        "jazz piano trio private press obscure",
        "rhodes ballad brazilian 1976 instrumental",
        "keyboard library music kpm piano",
        "electric piano quiet storm instrumental 1981",
        "piano soul instrumental b side 45 rare",
        "rhodes city pop instrumental japan",
        "piano meditation private press 1977 lp",
        "fender rhodes spiritual jazz obscure",
        "clavinet funk instrumental rare lp",
        "piano theme library music italian 1972",
        "rhodes gospel instrumental rare",
        "japanese piano jazz obscure 1978 album",
        "piano mpb instrumental 1975 rare",
        "electric piano demo private press loner",
    ],
    "DARK": [
        "dark soul minor key instrumental rare",
        "melancholic library music 1973",
        "moody jazz obscure private press",
        "sombre soul ballad rare 45",
        "dark library music suspense 1975",
        "minor key soul instrumental b side",
        "haunting instrumental private press lp",
        "dark jazz funk obscure 1974 vinyl",
        "melancholic brazilian instrumental 1976",
        "nocturne library music strings rare",
        "dark psych soul instrumental obscure",
        "moody city pop japan minor",
        "melancholic gospel instrumental rare lp",
        "dark spiritual jazz private press",
        "sombre instrumental soundtrack 1972 rare",
        "minor key quiet storm instrumental 1982",
        "dark folk instrumental private press",
        "lament instrumental library music",
        "shadow theme library music 1970s",
        "melancholic rhodes instrumental obscure",
    ],
    "FOLK": [
        "loner folk private press 1972 lp",
        "acid folk obscure rare vinyl",
        "acoustic folk instrumental private press",
        "psych folk rare 1971 album",
        "folk private press fingerstyle guitar",
        "japanese folk psych 1975 obscure",
        "brazilian folk violao instrumental rare",
        "folk rock obscure private press 1973",
        "pastoral folk library music acoustic",
        "singer songwriter private press obscure 1974",
        "folk baroque instrumental guitar rare",
        "acid folk japan 1976 album",
        "acoustic guitar instrumental private press lp",
        "folk jazz obscure 1972 rare vinyl",
        "rural folk private press loner obscure",
        "folk psych instrumental interlude rare",
        "european folk library music 1974",
        "folk ballad private press 1975 obscure",
        "fingerpicking folk instrumental rare lp",
        "folk soul acoustic obscure 1973",
    ],
}


# Buscar un INSTRUMENTO en YouTube trae gente tocando, no discos: covers de
# Hey Jude en Wurlitzer, "Rhodes Chord", musica de fondo. Medido el 27-oct:
# de 415 resultados de PIANO, los que pasaban los filtros eran casi todos eso.
# Asi que se exige evidencia de prensado: un año, un formato, o un canal que ya
# rindio. Es el mismo principio que el resto del proyecto — la obra, no el video.
ANIO = mod_veta.re.compile(r"(?:19[4-9]|20[0-2])[0-9]")
FORMATO = mod_veta.rx("lp", "ep", "45", "7 inch", "vinyl", "vinilo",
                      "private press", "library", "kpm", "ost", "soundtrack",
                      "album", "lado b", "b side", "bside", "reissue",
                      "acetate", "test pressing", "compilation", "sello")
NO_ES_DISCO = mod_veta.rx("cover", "covered", "my version", "arrangement",
                          "arranged by", "played on", "playing", "background music",
                          "ambient mood", "chord", "chords", "lesson", "tutorial",
                          "how to", "demo", "practice", "improv", "jam session",
                          "live session", "performance", "recital", "transcription")


def es_disco(x):
    """Evidencia de que esto es un prensado y no un video casero."""
    t = x["titulo"] or ""
    if NO_ES_DISCO.search(t):
        return False
    if (x["canal"] or "") in getattr(criterios, "CANALES", {}):
        return True
    return bool(ANIO.search(t) or FORMATO.search(t))


def cavar(nombre, cupo):
    queries = QUERIES[nombre]
    print("cavando %s con %d queries…" % (nombre, len(queries)))

    crudo = {}
    with ThreadPoolExecutor(max_workers=5) as ex:
        for lote in ex.map(srv.ytsearch, queries):
            for x in lote:
                crudo.setdefault(x["id"], x)
    print("  YouTube devolvio %d temas distintos" % len(crudo))

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    ya = {r[0] for r in con.execute("SELECT id FROM tema")}
    enhot = {r[0] for r in con.execute("SELECT id FROM hotlist")}

    pasan, desc = [], {}
    for vid, x in crudo.items():
        if vid in ya or vid in enhot:
            desc["ya lo tenias"] = desc.get("ya lo tenias", 0) + 1
            continue
        motivo = criterios.descartar(x["titulo"], x["dur"], x["views"], x["canal"])
        if motivo:
            desc[motivo] = desc.get(motivo, 0) + 1
            continue
        if not es_disco(x):
            desc["no parece un disco"] = desc.get("no parece un disco", 0) + 1
            continue
        sen, raz_v = mod_veta.senal(x["titulo"], x["canal"], None, None, nombre)
        if sen < 1.0:
            desc["no es de la veta"] = desc.get("no es de la veta", 0) + 1
            continue
        pts, raz = criterios.puntuar(x["titulo"], x["dur"], x["views"], x["canal"])
        pasan.append((pts + sen, ["veta " + nombre] + raz_v + raz, x))

    print("  pasan los filtros: %d" % len(pasan))
    for k, v in sorted(desc.items(), key=lambda kv: -kv[1])[:5]:
        print("     %-42s %d" % (k[:42], v))

    pasan.sort(key=lambda x: -x[0])
    elegidos, por_canal, por_art = [], {}, {}
    for pts, raz, x in pasan:
        c = x["canal"] or "?"
        a = criterios.quitar_tildes((x["titulo"] or "").split(" - ")[0])[:22]
        if por_canal.get(c, 0) >= 3 or por_art.get(a, 0) >= 2:
            continue
        por_canal[c] = por_canal.get(c, 0) + 1
        por_art[a] = por_art.get(a, 0) + 1
        elegidos.append((pts, raz, x))
        if len(elegidos) >= cupo:
            break

    print("\n  entran %d:" % len(elegidos))
    for pts, raz, x in elegidos[:10]:
        print("     %+5.1f  %-56s" % (pts, (x["titulo"] or "")[:56]))
        print("            %s" % " · ".join(raz[:3])[:68])

    if VER:
        print("\n(--ver: no guarde nada)")
        con.close()
        return 0

    hoy = time.strftime("%Y-%m-%d")
    for pts, raz, x in elegidos:
        art, nom = srv.partir(x["titulo"])
        con.execute("""INSERT OR IGNORE INTO tema(id,titulo,artista,nombre,canal,
                                                  duracion,views,agregado)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (x["id"], x["titulo"], art, nom, x["canal"],
                     x["dur"], x["views"], hoy))
        con.execute("INSERT OR IGNORE INTO origen(id,fuente) VALUES(?,'cavado')",
                    (x["id"],))
        con.execute("""INSERT OR REPLACE INTO hotlist(id,pts,razones,tanda,agregado)
                       VALUES(?,?,?,?,?)""",
                    (x["id"], pts, json.dumps(raz, ensure_ascii=False),
                     "cavado-" + nombre.lower(), hoy))
    con.commit()
    vivos = con.execute("SELECT count(*) FROM hot").fetchone()[0]
    print("\n  guardados: %d  ->  hotlist con %d esperandote" % (len(elegidos), vivos))
    con.close()
    return 0


def main():
    pedidas = [a.upper() for a in sys.argv[1:] if a.upper() in QUERIES]
    if not pedidas:
        print("decime que veta: %s" % ", ".join(QUERIES))
        return 1
    for n in pedidas:
        cavar(n, CUPO)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
