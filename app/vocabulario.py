# -*- coding: utf-8 -*-
"""Genera vetas combinando estilo + pais + decada, con el vocabulario real.

Thomas, 4-nov, sobre samplette.io: "como podemos explotar esta web tambien,
otra fuente mas de data".

Lo que de esa web sirve NO es su catalogo —eso es su producto, y ademas sale
de Discogs y YouTube, que ya consultamos directo— sino su VOCABULARIO, que es
publico y es la taxonomia de Discogs: 739 estilos y 241 paises.

Por que importa: las ESCENAS de criterios.py son diecinueve, escritas a mano.
Con el vocabulario se arman miles de vetas del tipo "Bulgarian Prog Rock
1976", que es exactamente el formato que a Thomas le funciono cuando lo leimos
de @offtherecordsamples y saco a The Blue Effect con 743 views.

No se combina a lo bruto (739 x 241 x decadas = millones): se cruza contra lo
que Thomas YA guarda, para que las vetas salgan de su oido y no de un
producto cartesiano.

Uso:
    python vocabulario.py              propone vetas nuevas
    python vocabulario.py --cavar      ademas las cava y las deja en la cola
    python vocabulario.py --bajar      refresca la taxonomia
"""
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import criterios

DB = r"G:\Thomi - Mi Carpeta\crate_project\crate.db"
VOC = os.path.join(HERE, "datos", "vocabulario.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0"

# Los estilos de Discogs que tienen sentido para un beatmaker de hiphop con
# el oido de Thomas. Sacados de los 739 que existen: el resto (metal, techno,
# opera, spoken word) no entra en un beat drumless ni en broma.
UTILES = re.compile(
    r"soul|funk|disco|boogie|jazz|fusion|bossa|samba|mpb|latin|afro|"
    r"psych|prog|folk|library|soundtrack|score|easy listening|lounge|"
    r"rhythm & blues|rnb|gospel|blues|city pop|kayo|enka|ye-?ye|"
    r"chanson|beat|garage|tropical|cumbia|salsa|highlife|ethio|"
    r"ambient|modal|spiritual|fado|raga|sunshine pop|baroque pop", re.I)

# Paises que de verdad tienen escenas sampleables y poco cavadas. Los que ya
# estan en ESCENAS no hace falta repetirlos.
PAISES = ["Czechoslovakia", "USSR", "Bulgaria", "Poland", "Hungary",
          "Yugoslavia", "Romania", "East Germany", "Thailand", "Japan",
          "Brazil", "Peru", "Colombia", "Nigeria", "Ethiopia", "Turkey",
          "Greece", "Italy", "France", "Germany", "Spain", "Mexico",
          "Argentina", "Indonesia", "India", "Korea", "Sweden", "Finland"]

DECADAS = ["1969", "1972", "1974", "1976", "1978", "1981"]


def bajar_vocabulario():
    """Trae la taxonomia. Son tres listas publicas, no el catalogo de nadie."""
    out = {}
    for nombre, url in (("generos", "https://samplette.io/genres_lov"),
                        ("estilos", "https://samplette.io/styles_lov"),
                        ("paises", "https://samplette.io/countries_lov")):
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Referer": "https://samplette.io/"})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        lista = d if isinstance(d, list) else list(d.values())[0]
        out[nombre] = [x if isinstance(x, str) else list(x.values())[0] for x in lista]
        print("  %-9s %d" % (nombre, len(out[nombre])))
        time.sleep(1)                      # una por segundo, sin apurar
    os.makedirs(os.path.dirname(VOC), exist_ok=True)
    with open(VOC, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return out


def cargar():
    if os.path.exists(VOC):
        with open(VOC, encoding="utf-8") as f:
            return json.load(f)
    print("bajando el vocabulario por primera vez...")
    return bajar_vocabulario()


def estilos_de_thomas(con, estilos):
    """Que estilos aparecen en lo que YA guardo, por sus titulos.

    Es la unica forma honesta de elegir: no se trata de que estilos existen
    sino de cuales estan en su crate. Lo demas seria adivinar.
    """
    titulos = " ".join(r[0] or "" for r in con.execute("""
        SELECT t.titulo FROM tema t
        WHERE EXISTS (SELECT 1 FROM en_playlist p WHERE p.id = t.id)
           OR EXISTS (SELECT 1 FROM marca m WHERE m.id=t.id AND m.estrellas >= 3)
    """)).lower()
    vistos = []
    for e in estilos:
        if not UTILES.search(e):
            continue
        if e.lower() in titulos:
            vistos.append((titulos.count(e.lower()), e))
    vistos.sort(reverse=True)
    return vistos


def main():
    if "--bajar" in sys.argv:
        print("refrescando el vocabulario...")
        bajar_vocabulario()
        return 0

    voc = cargar()
    con = sqlite3.connect(DB)
    print("vocabulario: %d estilos, %d paises" % (len(voc["estilos"]), len(voc["paises"])))

    suyos = estilos_de_thomas(con, voc["estilos"])
    print()
    print("estilos que YA aparecen en tu crate (de los %d que existen):" % len(voc["estilos"]))
    for n, e in suyos[:14]:
        print("   %-26s %3d veces" % (e, n))

    # las vetas nuevas: sus estilos cruzados con paises poco cavados
    ya = set()
    for qs in criterios.ESCENAS.values():
        ya.update(q.lower() for q in qs)

    propuestas = []
    for _, est in suyos[:10]:
        for pais in PAISES:
            for dec in DECADAS[:2]:
                q = "%s %s %s vinyl" % (pais.lower(), est.lower(), dec)
                if q not in ya:
                    propuestas.append(q)
    print()
    print("vetas que se pueden armar con eso: %d" % len(propuestas))
    print("ejemplos:")
    for q in propuestas[:12]:
        print("   %s" % q)

    if "--cavar" not in sys.argv:
        print()
        print("para cavarlas:  python vocabulario.py --cavar")
        con.close()
        return 0

    import crate_server as srv
    from concurrent.futures import ThreadPoolExecutor
    hoy, semana = time.strftime("%Y-%m-%d"), time.strftime("%Y-S%V")
    sel = propuestas[:28]
    print()
    print("cavando %d vetas..." % len(sel))

    def b(q):
        try:
            return q, srv.ytsearch(q, n=12)
        except Exception:
            return q, []

    yaid = {r[0] for r in con.execute("SELECT id FROM tema")}
    crudo, nuevos = {}, 0
    with ThreadPoolExecutor(max_workers=5) as ex:
        for q, res in ex.map(b, sel):
            for x in res:
                if x["id"] not in crudo:
                    x["veta"] = q
                    crudo[x["id"]] = x
    pasan = []
    for vid, x in crudo.items():
        if criterios.descartar(x["titulo"], x["dur"], x["views"], x["canal"]):
            continue
        pts, raz = criterios.puntuar(x["titulo"], x["dur"], x["views"], x["canal"])
        pasan.append((pts, ["veta " + x["veta"]] + raz, x))
        if vid not in yaid:
            art, nom = srv.partir(x["titulo"])
            con.execute("""INSERT OR IGNORE INTO tema(id,titulo,artista,nombre,
                                     canal,duracion,views,agregado)
                           VALUES(?,?,?,?,?,?,?,?)""",
                        (vid, x["titulo"], art, nom, x["canal"], x["dur"],
                         x["views"], hoy))
            con.execute("INSERT OR IGNORE INTO origen(id,fuente) VALUES(?,'vocabulario')",
                        (vid,))
            nuevos += 1
    pasan.sort(key=lambda t: -t[0])
    vistos, eleg = set(), []
    for pts, raz, x in pasan:
        k = criterios.quitar_tildes((x["titulo"] or "").split(" - ")[0])[:20]
        if k in vistos:
            continue
        vistos.add(k)
        eleg.append((pts, raz, x))
        if len(eleg) >= 40:
            break
    for pts, raz, x in eleg:
        con.execute("""INSERT OR REPLACE INTO hotlist(id,pts,razones,genero,tanda,agregado)
                       VALUES(?,?,?,?,?,?)""",
                    (x["id"], pts, json.dumps(raz, ensure_ascii=False),
                     criterios.genero_de(x["titulo"], x["canal"]) or "JAZZ FUSION",
                     "vocab-" + semana, hoy))
    con.commit()
    print("  crudos %d | pasan %d | nuevos %d | al hotlist %d"
          % (len(crudo), len(pasan), nuevos, len(eleg)))
    print()
    for pts, raz, x in eleg[:12]:
        v = x["views"]
        print("  %+4.1f %-48s %6s  %s" % (pts, x["titulo"][:48],
              ("%dk" % (v // 1000)) if v and v >= 1000 else v, raz[0][:30]))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
