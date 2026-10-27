# -*- coding: utf-8 -*-
"""HTML de la revision de las 5 playlists: que mover, que sacar, que decidir.
Archivo nuevo, no toca ninguna lista de sugerencias."""
import json, os, re, html
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = r"G:\Thomi - Mi Carpeta\crate_project\revision-playlists.html"
P = json.load(open(os.path.join(HERE, "pl_pool.json"), encoding="utf-8"))
M = json.load(open(os.path.join(HERE, "meta_cache.json"), encoding="utf-8"))
SNIP = open(os.path.join(HERE, "marks_snippet.html"), encoding="utf-8").read()

NOM = {"80s": "80s", "soul": "SOUL", "rnb": "R&B SOUL",
       "citypop": "CITY POP", "fusion": "JAZZ FUSION"}

def art(vid, e):
    u = (M.get(vid, {}).get("uploader") or e.get("uploader") or "")
    return u.replace(" - Topic", "").strip()

def anio(vid):
    y = M.get(vid, {}).get("year")
    return y if y and str(y).isdigit() else "?"

GRUPOS = [
 ("sacar", "Sacar de la lista",
  "Gio Gomez son 34 beats de un productor actual (DistroKid, 2025) con el BPM "
  "en el titulo: 10 en tu lista de 80s y 24 en la de fusion, que es el 12% de esa "
  "lista. De los 33 que declaran tempo, 19 estan arriba de 115 BPM. Si los pusiste "
  "a proposito ignorame; si no, son 34 lugares ocupados.",
  lambda vid, e: art(vid, e) in ("Gio Gomez", "Mac DeMarco")),
 ("mover", "Mover de lista",
  "Lonnie Liston Smith es fusion, no soul ni R&B. 'Peaceful Ones' ademas esta "
  "duplicado en dos listas.",
  lambda vid, e: "lonnie liston" in e["title"].lower()),
 ("dup", "Estan en dos listas a la vez",
  "El mismo video cargado en dos de tus listas. Decidi cual queda.",
  lambda vid, e: len(e["listas"]) > 1 and "lonnie liston" not in e["title"].lower()),
 ("decidir", "Suenan a epoca pero son actuales",
  "Grabados ahora, no reediciones. Si te sirven igual, se quedan: es tu criterio.",
  lambda vid, e: art(vid, e) in ("Jalen Ngonda", "Henry Porter")),
]
CSS = """body{font-family:system-ui,sans-serif;max-width:1000px;margin:24px auto;padding:0 16px;background:#f4efe6;color:#2a2420}
h1{font-size:1.4rem}h2{font-size:1.05rem;margin-top:2rem;border-bottom:2px solid #c9b8a0;padding-bottom:4px}
table{width:100%;border-collapse:collapse}td{padding:6px 8px;border-bottom:1px solid #e0d6c4;vertical-align:top;font-size:.92rem}
td.n{color:#8a7a66;width:2.4em;text-align:right}td.m{width:12em;color:#6b5d4d;font-size:.84rem;white-space:nowrap}
a{color:#8b2f1f;text-decoration:none;font-weight:600}a:hover{text-decoration:underline}
.ch{color:#6b5d4d;font-size:.82rem}.sub{color:#4a4038;font-size:.88rem;margin:6px 0 10px}
.nota{background:#efe6d2;border:1px solid #c9b8a0;padding:10px 14px;border-radius:6px;margin:12px 0;font-size:.9rem}
.lista{display:inline-block;background:#d9cdb5;border-radius:3px;padding:1px 6px;font-size:.78rem;margin-right:4px}"""

out = ['<!doctype html><html lang="es"><head><meta charset="utf-8">'
       '<title>Revisión de tus 5 listas</title><style>%s</style></head><body>' % CSS,
 '<h1>Revisión de tus 5 playlists</h1>',
 '<div class="nota"><b>662 temas revisados</b> — fusion 205, soul 157, R&B 138, 80s 124, '
 'city pop 42.<br><br>Abajo solo lo que hay que decidir. El resto está bien catalogado.<br><br>'
 '<b>Lo que NO está acá y mi análisis marcó mal:</b> Surface, Kashif, Howard Hewett, '
 'Herb Alpert, Aurra, The Montclairs, Brighter Side of Darkness. Salían con año 2006–2015 '
 'porque el ℗ es de la redistribución digital, pero la música es de su época. '
 'Era un bug mío leyendo el ℗ (el sello "709044 Records DK" me daba el año 7090).'
 '<br><br><b>Este archivo es nuevo, no toca ninguna de tus listas de sugerencias.</b></div>']

for slug, titulo, sub, test in GRUPOS:
    items = [(vid, e) for vid, e in P.items() if test(vid, e)]
    if not items:
        continue
    items.sort(key=lambda t: (art(*t), t[1]["title"]))
    out.append("<h2>%s (%d)</h2>" % (html.escape(titulo), len(items)))
    out.append('<div class="sub">%s</div><table>' % html.escape(sub))
    for i, (vid, e) in enumerate(items, 1):
        ls = "".join('<span class="lista">%s</span>' % NOM[L] for L in e["listas"])
        d = e.get("dur") or 0
        out.append(
            '<tr><td class="n">%d</td><td><a href="https://www.youtube.com/watch?v=%s" '
            'target="_blank">%s</a><div class="ch">%s</div><div>%s</div></td>'
            '<td class="m">%s<br>%d:%02d</td></tr>'
            % (i, vid, html.escape(e["title"][:84]), html.escape(art(vid, e)), ls,
               anio(vid), d // 60, d % 60))
    out.append("</table>")

out.append(SNIP + "</body></html>")
open(OUT, "w", encoding="utf-8").write("\n".join(out))
tot = sum(1 for vid, e in P.items() if any(t(vid, e) for _, _, _, t in GRUPOS))
print("%d temas a decidir, de %d -> %s" % (tot, len(P), OUT))
