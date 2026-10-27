# -*- coding: utf-8 -*-
"""Los 79 de la lista SOUL que Thomas no abrio, reordenados por lo unico medido:
el tier a mano (fuego 58% / bien 38% sobre 153 marcas suyas).

No puedo filtrarlos mas: los 4 canales de esta lista no tienen ni un dato de
feedback todavia. Por eso van agrupados por canal, para que marcando pocos de
cada uno quede medido el canal y la proxima si se pueda filtrar."""
import json, os, re, html
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = r"G:\Thomi - Mi Carpeta\crate_project\repaso-soul.html"
R = json.load(open(os.path.join(HERE, "repaso.json"), encoding="utf-8"))
meta = json.load(open(os.path.join(HERE, "meta_cache.json"), encoding="utf-8"))
bpm = json.load(open(os.path.join(HERE, "bpm_cache.json"), encoding="utf-8"))
SNIP = open(os.path.join(HERE, "marks_snippet.html"), encoding="utf-8").read()

queda, fuera = R["queda"], R["fuera"]
TIER = {"fuego": "\U0001F525", "bien": "\U0001F44D", "quizas": "\U0001F914"}

def vs(v):
    if v is None: return "?"
    return "%.1fM" % (v / 1e6) if v >= 1e6 else ("%dk" % (v // 1000) if v >= 1000 else str(v))

def tempo(vid):
    b = bpm.get(vid, {}).get("bpm")
    if not b: return "? BPM"
    if b > 115 and 55 <= b / 2 <= 115:
        return "%d BPM <span class=alt>(leyó %d)</span>" % (round(b / 2), round(b))
    return "%d BPM" % round(b)

CSS = """body{font-family:system-ui,sans-serif;max-width:1020px;margin:24px auto;padding:0 16px;background:#f4efe6;color:#2a2420}
h1{font-size:1.4rem}h2{font-size:1.04rem;margin-top:2.2rem;border-bottom:2px solid #c9b8a0;padding-bottom:4px}
table{width:100%;border-collapse:collapse}td{padding:6px 8px;border-bottom:1px solid #e0d6c4;vertical-align:top;font-size:.92rem}
td.n{color:#8a7a66;width:2.4em;text-align:right}td.m{width:10.5em;color:#6b5d4d;font-size:.84rem;white-space:nowrap}
a{color:#8b2f1f;text-decoration:none;font-weight:600}a:hover{text-decoration:underline}
.ch{color:#6b5d4d;font-size:.82rem}.why{color:#4a4038;font-size:.86rem;margin-top:2px}
.alt{color:#9a8c7c;font-size:.78rem}.men{color:#5a6a4a;font-weight:600}
.nota{background:#efe6d2;border:1px solid #c9b8a0;padding:10px 14px;border-radius:6px;margin:12px 0;font-size:.9rem}
.out{opacity:.55;text-decoration:line-through}.sub{color:#4a4038;font-size:.88rem;margin:6px 0 10px}"""

out = ['<!doctype html><html lang="es"><head><meta charset="utf-8">'
       '<title>Repaso · SOUL sin abrir</title><style>%s</style></head><body>' % CSS,
 "<h1>Los %d de SOUL que no abriste, reordenados</h1>" % len(queda),
 '<div class="nota"><b>Qué hice:</b> pasé por la lógica corregida los temas que todavía no '
 'abriste. Son todos de la lista de SOUL, la única de la que no me diste feedback.<br><br>'
 '<b>Lo que NO pude hacer:</b> filtrarlos. Los 4 canales de esta lista no tienen un solo '
 'dato tuyo todavía, así que no tengo con qué descartar. Te miento si te digo otra cosa.<br><br>'
 '<b>Lo que sí:</b> ordenarlos por lo único que está medido de verdad — el tier a mano, que '
 'sobre tus 153 marcas da <b>🔥 58%</b> contra <b>👍 38%</b>. Los 🔥 van primero. '
 'Si escuchás solo esos, deberías guardar cerca de la mitad.<br><br>'
 '<b>Van agrupados por canal</b> a propósito: marcando unos pocos de cada uno, el canal queda '
 'medido y la próxima vez sí puedo filtrar. Hoy son los 4 canales ciegos que me quedan.<br><br>'
 'Ojo que el hit rate real es <b>42%</b>, no 59% como te dije antes: lo que abriste y no '
 'guardaste cuenta como rechazo.<br><br>'
 '<b>Archivo nuevo: no toca tu sugerencias-v2-soul.html.</b></div>']

if fuera:
    out.append("<h2>Estos salen (%d)</h2>" % len(fuera))
    out.append('<div class="sub">Duran menos de 2:30. "Corto" es un motivo que ya usaste.</div><table>')
    for i, e in enumerate(fuera, 1):
        d = e.get("dur") or 0
        out.append('<tr><td class="n">%d</td><td class="out">%s</td>'
                   '<td class="m">%d:%02d</td></tr>'
                   % (i, html.escape(e["title"][:80]), d // 60, d % 60))
    out.append("</table>")

orden = {"fuego": 0, "bien": 1, "quizas": 2}
por_canal = {}
for e in queda:
    por_canal.setdefault(e["uploader"], []).append(e)

i = 0
for canal in sorted(por_canal, key=lambda c: -sum(1 for x in por_canal[c] if x["tier"] == "fuego")):
    it = sorted(por_canal[canal], key=lambda x: orden.get(x["tier"], 3))
    f = sum(1 for x in it if x["tier"] == "fuego")
    out.append("<h2>%s — %d temas (%d 🔥)</h2>" % (html.escape(canal), len(it), f))
    out.append('<div class="sub">Canal sin medir. Marcá unos pocos y queda calibrado.</div><table>')
    for e in it:
        i += 1
        vid = e["id"]
        m = meta.get(vid, {})
        b = bpm.get(vid, {})
        key = b.get("key") or ""
        kc = ' class="men"' if "minor" in key else ""
        d = e.get("dur") or 0
        v = m.get("views") if m.get("views") is not None else e.get("views")
        info = "%s<br>%s%s<br>%s views · %d:%02d" % (
            m.get("year") or "?", tempo(vid),
            (" · <span%s>%s</span>" % (kc, key)) if key else "",
            vs(v), d // 60, d % 60)
        out.append('<tr><td class="n">%d</td><td>%s <a href="https://www.youtube.com/watch?v=%s" '
                   'target="_blank">%s</a><div class="why">%s</div></td>'
                   '<td class="m">%s</td></tr>'
                   % (i, TIER.get(e["tier"], ""), vid, html.escape(e["title"][:90]),
                      html.escape(e.get("why", "")), info))
    out.append("</table>")

out.append(SNIP + "</body></html>")
open(OUT, "w", encoding="utf-8").write("\n".join(out))
print("%d para escuchar (%d 🔥) | %d descartados -> %s"
      % (len(queda), sum(1 for e in queda if e["tier"] == "fuego"), len(fuera), OUT))
