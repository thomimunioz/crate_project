# -*- coding: utf-8 -*-
"""Los discos CONCRETOS que muestran las cuentas de IG, buscados y guardados.

Thomas, 4-nov: "encontraste todos los samples que te pase de los videos de
IG? porque al fin y al cabo yo queria eso. Mas que encontrar la veta
encontrar los samples".

Tenia razon en el reclamo: habia leido las portadas y nombrado algunos discos
al pasar, pero nunca los busque ni los guarde. Esto hace eso.

Cada entrada salio de MIRAR la portada en la hoja de contacto, no de adivinar.
"""
import json
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor

APP = r"G:\Thomi - Mi Carpeta\crate_project\app"
sys.path.insert(0, APP)
import criterios
import crate_server as srv

DB = r"G:\Thomi - Mi Carpeta\crate_project\crate.db"

# (cuenta, busqueda). Lo que se lee en cada portada.
DISCOS = [
    # --- @digginworldwide: soul, jazz y library de EEUU ---
    ("digginworldwide", "Joe Thomas Joy Of Cookin"),
    ("digginworldwide", "Phil Upchurch Free And Easy"),
    ("digginworldwide", "Lonnie Smith Funk Reaction"),
    ("digginworldwide", "Howard Roberts Antelope Freeway"),
    ("digginworldwide", "Derek Austin Sound Stage 16"),
    ("digginworldwide", "Shelly Manne Mannekind"),
    ("digginworldwide", "Cal Tjader Sounds Out Burt Bacharach"),
    ("digginworldwide", "Jimmy McGriff Friday the 13th Cook County Jail"),
    ("digginworldwide", "Vince Guaraldi You're A Good Sport Charlie Brown"),
    ("digginworldwide", "Decatur Park District Summer Staff Singers"),
    ("digginworldwide", "Moonshade De Wolfe library"),

    # --- @lightnup_records: rare groove japones y OST ---
    ("lightnup_records", "Yuji Ohno Space Kid 大野雄二"),
    ("lightnup_records", "Masaru Sato Sugata Sanshiro 姿三四郎"),
    ("lightnup_records", "中村晃子 Akiko Nakamura best album"),
    ("lightnup_records", "浅丘ルリ子 Ruriko Asaoka 愛を歌う"),
    ("lightnup_records", "悪魔の手毬唄 soundtrack"),
    ("lightnup_records", "まんが日本史 音楽集"),
    ("lightnup_records", "四季 Japanese jazz Toho records"),

    # --- @portal___records: Japon entero ---
    ("portal___records", "Jun Fukamachi Tale of the Heike"),
    ("portal___records", "Pacific Jam japanese fusion"),
    ("portal___records", "麻生よう子 逃避行 Yoko Aso"),
    ("portal___records", "Ayumi Ishida Lonely Night"),
    ("portal___records", "梶芽衣子 Meiko Kaji"),
    ("portal___records", "Hideko Okiyama Summertime"),
    ("portal___records", "Lupin the 3rd BGM Yuji Ohno"),

    # --- @sovietfreestyle: sovietico, tailandes, japones ---
    ("sovietfreestyle", "Valentina Tolkunova Валентина Толкунова"),
    ("sovietfreestyle", "Андрей Мисин Чужой Andrei Misin"),
    ("sovietfreestyle", "Mineko Yamada Harmagedon Story"),

    # --- @uptowndiggin: soul y boogie de EEUU ---
    ("uptowndiggin", "Ahmad Jamal The Awakening"),
    ("uptowndiggin", "Michael Boothman Touch"),
    ("uptowndiggin", "Gil Scott-Heron Free Will"),
    ("uptowndiggin", "Oby Onyioha"),
    ("uptowndiggin", "Alice Clark"),
    ("uptowndiggin", "Sunburn Capitol soul 1979"),
]


def main():
    hoy = time.strftime("%Y-%m-%d")
    semana = time.strftime("%Y-S%V")
    con = sqlite3.connect(DB)
    ya = {r[0] for r in con.execute("SELECT id FROM tema")}
    marcados = {r[0] for r in con.execute("SELECT id FROM marca")}

    print("buscando %d discos leidos de las portadas...\n" % len(DISCOS))

    def buscar(par):
        cuenta, q = par
        try:
            return cuenta, q, srv.ytsearch(q, n=8)
        except Exception:
            return cuenta, q, []

    nuevos, candidatos, sin_nada = 0, [], []
    with ThreadPoolExecutor(max_workers=4) as ex:
        for cuenta, q, res in ex.map(buscar, DISCOS):
            buenos = []
            for x in res:
                if x["id"] in marcados:
                    continue
                if criterios.descartar(x["titulo"], x["dur"], x["views"], x["canal"]):
                    continue
                buenos.append(x)
            if not buenos:
                sin_nada.append(q)
                continue
            print("  %-42s %d" % (q[:42], len(buenos)))
            for x in buenos[:3]:              # los tres mejores de cada disco
                if x["id"] not in ya:
                    art, nom = srv.partir(x["titulo"])
                    con.execute("""INSERT OR IGNORE INTO tema(id,titulo,artista,nombre,
                                           canal,duracion,views,agregado)
                                   VALUES(?,?,?,?,?,?,?,?)""",
                                (x["id"], x["titulo"], art, nom, x["canal"],
                                 x["dur"], x["views"], hoy))
                    con.execute("INSERT OR IGNORE INTO origen(id,fuente) VALUES(?,'ig-disco')",
                                (x["id"],))
                    nuevos += 1
                pts, raz = criterios.puntuar(x["titulo"], x["dur"], x["views"], x["canal"])
                candidatos.append((pts, ["de @" + cuenta] + raz, x))

    print("\n  temas nuevos en la base: %d" % nuevos)
    if sin_nada:
        print("  sin resultados utiles : %d (%s)" % (len(sin_nada), ", ".join(sin_nada[:3])[:60]))

    # a la cola, uno por disco para que no la copen tres versiones del mismo
    candidatos.sort(key=lambda t: -t[0])
    vistos, eleg = set(), []
    for pts, raz, x in candidatos:
        k = criterios.quitar_tildes((x["titulo"] or "").split(" - ")[0])[:20]
        if k in vistos:
            continue
        vistos.add(k)
        eleg.append((pts, raz, x))
    for pts, raz, x in eleg:
        con.execute("""INSERT OR REPLACE INTO hotlist(id,pts,razones,genero,tanda,agregado)
                       VALUES(?,?,?,?,?,?)""",
                    (x["id"], pts, json.dumps(raz, ensure_ascii=False),
                     criterios.genero_de(x["titulo"], x["canal"]) or "JAZZ FUSION",
                     "ig-discos-" + semana, hoy))
    con.commit()
    print("  al hotlist            : %d" % len(eleg))
    print("  hotlist total         : %d" % con.execute(
        "SELECT count(*) FROM hot").fetchone()[0])
    print()
    for pts, raz, x in eleg[:14]:
        v = x["views"]
        print("  %+4.1f %-50s %7s  %s" % (pts, x["titulo"][:50],
              ("%dk" % (v // 1000)) if v and v >= 1000 else v, raz[0]))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
