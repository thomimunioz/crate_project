# -*- coding: utf-8 -*-
"""HTML de la demo: 10 por genero, con la explicacion para alguien que no
conoce el proyecto. Archivo nuevo, no toca ninguna lista de Thomas."""
import json, os, re, html, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from demo_intro import INTRO

OUT = r"G:\Thomi - Mi Carpeta\crate_project\demo.html"
sel = json.load(open(os.path.join(HERE, "demo_final.json"), encoding="utf-8"))
meta = json.load(open(os.path.join(HERE, "meta_cache.json"), encoding="utf-8"))
bpm = json.load(open(os.path.join(HERE, "bpm_cache.json"), encoding="utf-8"))
stats = json.load(open(os.path.join(HERE, "demo_stats.json"), encoding="utf-8"))
SNIP = open(os.path.join(HERE, "marks_snippet.html"), encoding="utf-8").read()

GEN = [
 ("rnb", "R&B · modern soul de sello chico",
  "La veta que mejor rinde: 56% de acierto. Autoediciones de los 80, sellos que "
  "sacaron un disco y cerraron."),
 ("80s", "80s · quiet storm y slow jams",
  "R&B lento del 84 al 92. Lo que suena a las tres de la mañana."),
 ("soul", "Soul · 45s y private press de los 70",
  "Sweet soul, deep soul, Philly. Prensados chicos que no entraron a ninguna "
  "compilación."),
 ("citypop", "Japanese City Pop",
  "Japón 76-88. AOR y baladas con Rhodes, en discos que nunca salieron de ahí."),
 ("fusion", "Jazz Fusion · japonés y europeo",
  "Fusion mellow, eléctrico. Nada de trío de piano improvisando: eso no se "
  "puede samplear."),
]
TIER = {"fuego": "\U0001F525", "bien": "\U0001F44D"}

def mil(n):
    """Separador de miles con punto, como se escribe en espanol."""
    return "{:,}".format(n).replace(",", ".")


def vs(v):
    if v is None: return "?"
    return "%.1fM" % (v / 1e6) if v >= 1e6 else ("%dk" % (v // 1000) if v >= 1000 else str(v))

def tempo(vid):
    b = bpm.get(vid, {}).get("bpm")
    if not b: return "? BPM"
    if b > 115 and 55 <= b / 2 <= 115:
        return "%d BPM <span class=alt>(leyó %d)</span>" % (round(b / 2), round(b))
    return "%d BPM" % round(b)

CSS = """*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;max-width:1060px;margin:0 auto;padding:28px 18px 60px;background:#f4efe6;color:#2a2420;line-height:1.5}
h1{font-size:1.9rem;margin:0 0 4px;letter-spacing:-.5px}
.lede{color:#6b5d4d;font-size:1rem;margin:0 0 22px}
h2{font-size:1.1rem;margin:26px 0 6px}
.intro{background:#fffdf7;border:1px solid #d9cdb5;border-radius:10px;padding:18px 24px;margin:0 0 30px}
.intro h2{font-size:1.05rem;margin:22px 0 6px;color:#8b2f1f}
.intro h2:first-child{margin-top:0}
.intro p{margin:6px 0;font-size:.94rem}
.intro blockquote{margin:10px 0;padding:8px 14px;border-left:3px solid #c9b8a0;background:#f4efe6;font-style:italic;color:#4a4038;font-size:.92rem}
.sec{margin-top:38px}
.sec h2{font-size:1.18rem;border-bottom:2px solid #c9b8a0;padding-bottom:5px;margin-bottom:4px}
.sub{color:#6b5d4d;font-size:.88rem;margin:0 0 12px}
table{width:100%;border-collapse:collapse}
td{padding:8px;border-bottom:1px solid #e0d6c4;vertical-align:top;font-size:.93rem}
td.n{color:#8a7a66;width:2.4em;text-align:right}
td.m{width:11em;color:#6b5d4d;font-size:.83rem;white-space:nowrap;text-align:right}
a{color:#8b2f1f;text-decoration:none;font-weight:600}
a:hover{text-decoration:underline}
.ch{color:#6b5d4d;font-size:.81rem}
.why{color:#4a4038;font-size:.87rem;margin-top:3px}
.alt{color:#9a8c7c;font-size:.76rem}
.men{color:#5a6a4a;font-weight:600}
@media(max-width:640px){td.m{width:auto;font-size:.76rem}body{padding:16px 12px}}"""

out = ['<!doctype html><html lang="es"><head><meta charset="utf-8">'
       '<meta name="viewport" content="width=device-width,initial-scale=1">'
       '<title>CRATE · demo</title><style>%s</style></head><body>' % CSS,
       '<h1>CRATE</h1>',
       '<p class="lede">50 temas que probablemente no ibas a encontrar buscando. '
       '10 de cada género.</p>',
       INTRO.format(pool=mil(stats["pool"]), cand=mil(stats["cand"]),
                    medidos=stats["medidos"], marcas=stats["marcas"])]

n = 0
for slug, titulo, sub in GEN:
    it = sel.get(slug, [])
    if not it:
        continue
    out.append('<div class="sec"><h2>%s</h2><p class="sub">%s</p><table>'
               % (html.escape(titulo), html.escape(sub)))
    for e in it:
        n += 1
        vid = e["id"]
        m = meta.get(vid, {})
        b = bpm.get(vid, {})
        key = b.get("key") or ""
        kc = ' class="men"' if "minor" in key else ""
        d = e.get("dur") or 0
        v = m.get("views") if m.get("views") is not None else e.get("views")
        info = "%s<br>%s%s<br>%s · %d:%02d" % (
            m.get("year") or "?", tempo(vid),
            (" · <span%s>%s</span>" % (kc, key)) if key else "",
            vs(v), d // 60, d % 60)
        out.append('<tr><td class="n">%d</td><td>%s <a href="https://www.youtube.com/watch?v=%s" '
                   'target="_blank">%s</a><div class="ch">%s</div><div class="why">%s</div></td>'
                   '<td class="m">%s</td></tr>'
                   % (n, TIER.get(e.get("tier"), ""), vid, html.escape(e["title"][:92]),
                      html.escape(e.get("uploader") or ""), html.escape(e.get("why", "")), info))
    out.append("</table></div>")

out.append('<p class="sub" style="margin-top:30px">Tonalidades <span class="men">menores</span> '
           'resaltadas. El año sale del ℗ del distribuidor cuando está, si no del título. '
           'Tempo y tonalidad medidos sobre 45 s de audio real.</p>')
out.append(SNIP + "</body></html>")
open(OUT, "w", encoding="utf-8").write("\n".join(out))
print("%d temas -> %s" % (n, OUT))
