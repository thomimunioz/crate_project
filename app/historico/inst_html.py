# -*- coding: utf-8 -*-
"""HTML de la tanda de INSTRUMENTALES DE EPOCA. Archivo nuevo."""
import json, os, re, html
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = r"G:\Thomi - Mi Carpeta\crate_project\instrumentales.html"
pre = json.load(open(os.path.join(HERE, "inst_pre.json"), encoding="utf-8"))
meta = json.load(open(os.path.join(HERE, "meta_cache.json"), encoding="utf-8"))
bpm = json.load(open(os.path.join(HERE, "bpm_cache.json"), encoding="utf-8"))
SNIP = open(os.path.join(HERE, "marks_snippet.html"), encoding="utf-8").read()

def plegar(b):
    return b / 2 if b > 115 and 55 <= b / 2 <= 115 else b

def tipo(t):
    if re.search(r"\bdub\b", t, re.I): return "dub"
    if re.search(r"off ?vocal|\u30aa\u30d5\u30dc\u30fc\u30ab\u30eb", t, re.I): return "off vocal"
    if re.search(r"backing track|minus one|playback", t, re.I): return "backing"
    if re.search(r"\bunderscore\b", t, re.I): return "library"
    if re.search(r"\bTV (mix|track|size)\b", t, re.I): return "TV mix"
    return "instrumental"

POR_QUE = {
 "dub": "Dub: la voz entra y sale, y el resto es base pelada",
 "off vocal": "Off vocal: la cara B instrumental del single japonés",
 "backing": "Pista de acompañamiento, sin voz por definición",
 "library": "Library: grabado desde el vamos para ir debajo de algo",
 "TV mix": "Mezcla para TV: se hacía sin voz para cantar en vivo",
 "instrumental": "Instrumental del propio disco, no un karaoke moderno",
}

# se queda con lo medido, se ordena por tempo y se corta en 40
items = []
for x in pre:
    b = bpm.get(x["id"], {})
    if not b.get("bpm"):
        continue
    t = plegar(b["bpm"])
    if t > 112:                       # fuera de su rango
        continue
    x["bpm_real"] = t
    x["key"] = b.get("key") or ""
    x["tipo"] = tipo(x["title"])
    items.append(x)
items.sort(key=lambda y: (0 if "minor" in y["key"] else 1, y["bpm_real"]))
items = items[:40]

CSS = """*{box-sizing:border-box}
body{font-family:system-ui,sans-serif;max-width:1020px;margin:0 auto;padding:26px 16px 60px;background:#f4efe6;color:#2a2420;line-height:1.5}
h1{font-size:1.7rem;margin:0 0 4px}
.lede{color:#6b5d4d;margin:0 0 18px}
.nota{background:#fffdf7;border:1px solid #d9cdb5;border-radius:9px;padding:14px 20px;margin:0 0 24px;font-size:.93rem}
table{width:100%;border-collapse:collapse}
td{padding:7px 8px;border-bottom:1px solid #e0d6c4;vertical-align:top;font-size:.93rem}
td.n{color:#8a7a66;width:2.4em;text-align:right}
td.m{width:10.5em;color:#6b5d4d;font-size:.83rem;white-space:nowrap;text-align:right}
a{color:#8b2f1f;text-decoration:none;font-weight:600}a:hover{text-decoration:underline}
.ch{color:#6b5d4d;font-size:.81rem}.why{color:#4a4038;font-size:.86rem;margin-top:2px}
.men{color:#5a6a4a;font-weight:600}.alt{color:#9a8c7c;font-size:.76rem}
.tag{display:inline-block;background:#d9cdb5;border-radius:3px;padding:0 6px;font-size:.74rem;margin-left:6px;color:#4a4038}"""

men = sum(1 for x in items if "minor" in x["key"])
out = ['<!doctype html><html lang="es"><head><meta charset="utf-8">'
       '<meta name="viewport" content="width=device-width,initial-scale=1">'
       '<title>Instrumentales de época</title><style>%s</style></head><body>' % CSS,
 "<h1>Instrumentales de época</h1>",
 '<p class="lede">%d temas sin una sola voz. Ordenados por tonalidad menor '
 'primero y después por tempo.</p>' % len(items),
 '<div class="nota">Esto sale de lo que dijiste hoy: un instrumental no tiene '
 '<i>un hueco</i>, es todo hueco. Así que barrí las <b>50.900</b> del pool buscando '
 'las formas en que un disco de época declara que no trae voz: '
 '<b>instrumental</b>, <b>dub</b>, <b>off vocal</b> (la cara B del single japonés), '
 '<b>backing track</b>, <b>TV mix</b> y <b>underscore</b> de library.<br><br>'
 'Salieron <b>812</b>; quedaron <b>308</b> después de sacar lo ya visto, lo '
 'mainstream, los nombres conocidos, lo de menos de 2:45 y lo de menos de 150 '
 'reproducciones. De esos medí 60 y acá están los %d que entraron en tu rango de '
 'tempo. <b>%d en tonalidad menor.</b><br><br>'
 'Dejé afuera <i>"version"</i> a secas: en soul suele ser "7 Inch Version" y tiene '
 'voz. Y el karaoke moderno, que es MIDI y no sirve.</div>' % (len(items), men)]

out.append("<table>")
for i, x in enumerate(items, 1):
    m = meta.get(x["id"], {})
    v = m.get("views") if m.get("views") is not None else x.get("views")
    vs = "?" if v is None else ("%dk" % (v // 1000) if v >= 1000 else str(v))
    d = x.get("dur") or 0
    kc = ' class="men"' if "minor" in x["key"] else ""
    b = bpm.get(x["id"], {}).get("bpm")
    bt = ("%d BPM <span class=alt>(leyó %d)</span>" % (round(x["bpm_real"]), round(b))
          if b and b > 115 else "%d BPM" % round(x["bpm_real"]))
    out.append('<tr><td class="n">%d</td><td><a href="https://www.youtube.com/watch?v=%s" '
               'target="_blank">%s</a><span class="tag">%s</span>'
               '<div class="ch">%s</div><div class="why">%s</div></td>'
               '<td class="m">%s<br>%s · <span%s>%s</span><br>%s · %d:%02d</td></tr>'
               % (i, x["id"], html.escape(x["title"][:84]), x["tipo"],
                  html.escape(x.get("uploader") or ""), POR_QUE[x["tipo"]],
                  m.get("year") or "?", bt, kc, x["key"] or "?", vs, d // 60, d % 60))
out.append("</table>")
out.append(SNIP + "</body></html>")
open(OUT, "w", encoding="utf-8").write("\n".join(out))
from collections import Counter
print("%d temas (%d menores) -> %s" % (len(items), men, OUT))
print("por tipo: %s" % dict(Counter(x["tipo"] for x in items)))
