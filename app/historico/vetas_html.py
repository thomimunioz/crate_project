"""Genera los 5 HTML (uno por playlist) de la entrega de vetas de curadores."""
import json, os, html
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = r"G:\Thomi - Mi Carpeta\crate_project"
sel = json.load(open(os.path.join(HERE, "seleccion.json"), encoding="utf-8"))
meta = json.load(open(os.path.join(HERE, "meta_cache.json"), encoding="utf-8"))
try: bpm = json.load(open(os.path.join(HERE, "bpm_cache.json"), encoding="utf-8"))
except Exception: bpm = {}
SNIP = open(os.path.join(HERE, "marks_snippet.html"), encoding="utf-8").read()

PL = {
 "80s":   ("sugerencias-v2-80s.html",     "80s · quiet storm y slow jams"),
 "rnb":   ("sugerencias-v2-rnb.html",     "R&B Soul · modern soul de sello chico"),
 "soul":  ("sugerencias-v2-soul.html",    "Soul · 45s y private press de los 70"),
 "citypop":("sugerencias-v2-citypop.html","Japanese City Pop"),
 "fusion":("sugerencias-v2-fusion.html",  "Jazz Fusion · japonés y europeo"),
}
TIER = {"fuego": "🔥", "bien": "👍", "quizas": "🤔"}
CSS = """body{font-family:system-ui,sans-serif;max-width:1020px;margin:24px auto;padding:0 16px;background:#f4efe6;color:#2a2420}
h1{font-size:1.4rem}h2{font-size:1.02rem;margin-top:2.2rem;border-bottom:2px solid #c9b8a0;padding-bottom:4px}
table{width:100%;border-collapse:collapse}td{padding:6px 8px;border-bottom:1px solid #e0d6c4;vertical-align:top;font-size:.92rem}
td.n{color:#8a7a66;width:2.4em;text-align:right}td.m{width:10.5em;color:#6b5d4d;font-size:.84rem;white-space:nowrap}
a{color:#8b2f1f;text-decoration:none;font-weight:600}a:hover{text-decoration:underline}
.ch{color:#6b5d4d;font-size:.82rem}.why{color:#4a4038;font-size:.86rem;margin-top:2px}.alt{color:#9a8c7c;font-size:.78rem}
.nota{background:#efe6d2;border:1px solid #c9b8a0;padding:10px 14px;border-radius:6px;margin:12px 0;font-size:.9rem}
nav a{margin-right:14px;font-size:.9rem}.men{color:#5a6a4a;font-weight:600}"""

def vs(v):
    if v is None: return "?"
    return f"{v/1e6:.1f}M" if v >= 1e6 else f"{v//1000}k" if v >= 1000 else str(v)
def ds(d): return "?" if not d else f"{d//60}:{d%60:02d}"
def tempo(b):
    if not b: return "? BPM"
    if b > 115 and 55 <= b/2 <= 115: return f"{round(b/2)} BPM <span class=alt>(leyó {round(b)})</span>"
    return f"{round(b)} BPM"

nav = " ".join(f'<a href="{f}">{t.split(" · ")[0]}</a>' for k, (f, t) in PL.items())
hechos = []
for pl, (fname, titulo) in PL.items():
    items = [s for s in sel if s["playlist"] == pl]
    if not items: continue
    secciones = []
    for s in items:
        if s["seccion"] not in secciones: secciones.append(s["seccion"])
    out = [f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{html.escape(titulo)}</title><style>{CSS}</style></head><body>',
      f'<nav>{nav}</nav><h1>{html.escape(titulo)}</h1>',
      '<div class="nota"><b>De dónde salió esto:</b> en vez de buscar por palabras, caví <b>los canales de los que vos ya guardaste temas</b>. '
      'De un canal del que ya guardaste algo, guardás 16–22% de lo que sube; del resto, 3%. Son 27 curadores, '
      '<b>8.237 temas listados sin gastar quota</b>, filtrados contra todo lo que ya viste, y elegidos uno por uno.<br><br>'
      'Casi todo tiene entre <b>50 y 1.000 views</b>: son private press, 45s de sello chico y autoediciones japonesas. '
      'Usá el desplegable <b>✗ por qué no</b> en lo que descartes, y al final <b>💾 exportar feedback</b> — con eso afino la próxima.</div>']
    i = 0
    for secc in secciones:
        out.append(f"<h2>{html.escape(secc)}</h2><table>")
        for s in sorted([x for x in items if x["seccion"] == secc], key=lambda x: ["fuego","bien","quizas"].index(x["tier"])):
            i += 1; vid = s["id"]; m = meta.get(vid, {}); b = bpm.get(vid, {})
            year = m.get("year") or "?"
            key = b.get("key") or ""
            kcls = ' class="men"' if "minor" in key else ""
            views = m.get("views") if m.get("views") is not None else s.get("views")
            linea2 = tempo(b.get("bpm")) + (f' · <span{kcls}>{key}</span>' if key else "")
            info = f'{year}<br>{linea2}<br>{vs(views)} views · {ds(s.get("dur"))}'
            out.append(f'<tr><td class="n">{i}</td><td>{TIER[s["tier"]]} <a href="https://www.youtube.com/watch?v={vid}" target="_blank">{html.escape(s["title"][:95])}</a>'
                       f'<div class="ch">{html.escape(s["uploader"])}</div><div class="why">{html.escape(s["why"])}</div></td>'
                       f'<td class="m">{info}</td></tr>')
        out.append("</table>")
    out.append('<p class="ch">BPM y tonalidad medidos con el DSP de CRATE sobre 45 s de audio. Cuando el DSP lee la octava de arriba se muestra la mitad '
               'y entre paréntesis lo que leyó. Las tonalidades <span class="men">menores</span> van resaltadas. Año del ℗ o de la descripción.</p>')
    out.append(SNIP + "</body></html>")
    open(os.path.join(OUT, fname), "w", encoding="utf-8").write("\n".join(out))
    hechos.append((fname, i))
med = sum(1 for s in sel if "bpm" in bpm.get(s["id"], {}))
for f, n in hechos: print(f"{f}: {n} temas")
print(f"total {sum(n for _, n in hechos)} | con BPM medido: {med}/{len(sel)}")
