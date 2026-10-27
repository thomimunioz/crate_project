import json, os, html
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = r"G:\Thomi - Mi Carpeta\crate_project\sugerencias-latam.html"
short = json.load(open(os.path.join(HERE, "latam_short.json"), encoding="utf-8"))
meta = json.load(open(os.path.join(HERE, "meta_cache.json"), encoding="utf-8"))
try: bpm = json.load(open(os.path.join(HERE, "bpm_cache.json"), encoding="utf-8"))
except Exception: bpm = {}
SNIP = open(os.path.join(HERE, "marks_snippet.html"), encoding="utf-8").read()

def vs(v): return "?" if v is None else (f"{v/1e6:.1f}M" if v >= 1e6 else f"{v//1000}k" if v >= 1000 else str(v))
def ds(d): return "?" if not d else f"{d//60}:{d%60:02d}"

def tempo(b):
    """El DSP lee la octava de arriba en lo lento: si >115 y la mitad entra en 55–115, mostrar la mitad."""
    if not b: return "?", None
    if b > 115 and 55 <= b / 2 <= 115:
        return f"{round(b/2)} <span class=alt>(leyó {round(b)})</span>", b / 2
    return f"{round(b)}", b

TIER = {"fuego": "🔥", "bien": "👍", "quizas": "🤔"}
CSS = """body{font-family:system-ui,sans-serif;max-width:1020px;margin:24px auto;padding:0 16px;background:#f4efe6;color:#2a2420}
h1{font-size:1.4rem}h2{font-size:1.05rem;margin-top:2.2rem;border-bottom:2px solid #c9b8a0;padding-bottom:4px}
table{width:100%;border-collapse:collapse}td{padding:6px 8px;border-bottom:1px solid #e0d6c4;vertical-align:top;font-size:.92rem}
td.n{color:#8a7a66;width:2.4em;text-align:right}td.m{width:10.5em;color:#6b5d4d;font-size:.84rem;white-space:nowrap}
a{color:#8b2f1f;text-decoration:none;font-weight:600}a:hover{text-decoration:underline}
.ch{color:#6b5d4d;font-size:.82rem}.why{color:#4a4038;font-size:.86rem;margin-top:2px}.alt{color:#9a8c7c;font-size:.78rem}
.nota{background:#efe6d2;border:1px solid #c9b8a0;padding:10px 14px;border-radius:6px;margin:12px 0;font-size:.9rem}
nav a{margin-right:14px;font-size:.9rem}.men{color:#5a6a4a;font-weight:600}"""

capas = []
for s in short:
    if s["capa"] not in capas: capas.append(s["capa"])

out = [f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Sugerencias · LatAm</title><style>{CSS}</style></head><body>',
  '<nav><a href="sugerencias-80s.html">80s</a><a href="sugerencias-soul.html">Soul</a><a href="sugerencias-rnb-soul.html">R&B</a>'
  '<a href="sugerencias-city-pop.html">City pop</a><a href="sugerencias-jazz-fusion.html">Fusion</a><a href="sugerencias-tema-de-la-sierra.html">Tema de la Sierra</a></nav>',
  '<h1>Joyas de Latinoamérica — soul, fusion y 80s</h1>',
  '<div class="nota"><b>Calibrado con tu feedback de Cuba.</b> Lo que quedó afuera esta vez: lo efusivo y festivo, los ritmos cargados '
  '(guaguancó, carnaval, descarga), los tempos altos y los rips que suenan mal. Lo que busqué: <b>tonalidad menor, tempo bajo, ritmo simple, '
  'teclas y cuerdas, dramatismo</b>. Y nada de lo mainstream de Charly o Spinetta: de ellos solo va lo que es gema '
  '(Spinetta <em>Jade</em> instrumental, que es lo que ya venías guardando).<br><br>'
  '2.750 candidatos rastreados en 209 búsquedas más los Mix de seis temas que ya tenés guardados '
  '(Raíces, Grupo Encuentro, Cevasco, Oscar Moro, Montarroyos, Ornelas); 2.364 leídos uno por uno; 147 elegidos. '
  'BPM y tonalidad <b>medidos</b>, no estimados. '
  'Abajo de cada tema tenés el desplegable <b>✗ por qué no</b> para que yo aprenda de lo que descartás: cuando termines, '
  'tocá <b>💾 exportar feedback</b> arriba y pasame el archivo.</div>']

i = 0
for capa in capas:
    rows = [s for s in short if s["capa"] == capa]
    out.append(f"<h2>{html.escape(capa)}</h2><table>")
    for s in sorted(rows, key=lambda s: ["fuego", "bien", "quizas"].index(s["tier"])):
        i += 1; vid = s["id"]; m = meta.get(vid, {}); b = bpm.get(vid, {})
        year = m.get("year") or "?"
        tx, real = tempo(b.get("bpm"))
        key = b.get("key") or "?"
        kcls = ' class="men"' if "minor" in key else ""
        views = m.get("views") if m.get("views") is not None else s.get("views")
        info = f'{year}<br>{tx} BPM · <span{kcls}>{key}</span><br>{vs(views)} views · {ds(s.get("dur"))}'
        out.append(f'<tr><td class="n">{i}</td><td>{TIER[s["tier"]]} <a href="https://www.youtube.com/watch?v={vid}" target="_blank">{html.escape(s["title"])}</a>'
                   f'<div class="ch">{html.escape(s.get("uploader") or "?")}</div>'
                   f'<div class="why">{html.escape(s["why"])}</div></td><td class="m">{info}</td></tr>')
    out.append("</table>")

out.append('<p class="ch">BPM medido sobre 45 s desde el segundo 60 con el DSP de CRATE (Librosa). Cuando el DSP lee la octava de arriba '
           'se muestra la mitad y entre paréntesis lo que leyó. Las tonalidades menores van <span class="men">resaltadas</span>. '
           'Año del ℗ o de la descripción. Nada de esto está en tus 5 listas.</p>')
out.append(SNIP + "</body></html>")
open(OUT, "w", encoding="utf-8").write("\n".join(out))

med = [bpm[s["id"]]["bpm"] for s in short if "bpm" in bpm.get(s["id"], {})]
fold = [x/2 if x > 115 and 55 <= x/2 <= 115 else x for x in med]
men = sum(1 for s in short if "minor" in (bpm.get(s["id"], {}).get("key") or ""))
print(i, "temas →", OUT)
if fold:
    import statistics
    print(f"BPM medidos {len(fold)} | mediana {statistics.median(fold):.0f} | >115 reales: {sum(1 for x in fold if x>115)} | tonalidad menor: {men}/{len(short)}")
