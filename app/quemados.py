"""Revisión de los 66 fuego: riesgo de estar YA sampleado / ser conocido en el circuito de diggers.
Esto es conocimiento musical, no consulta a WhoSampled (bloqueado). Marca para verificar, no veredicto."""
import json, os, html
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = r"G:\Thomi - Mi Carpeta\crate_project\revision-quemados.html"
sel = json.load(open(os.path.join(HERE, "seleccion.json"), encoding="utf-8"))
meta = json.load(open(os.path.join(HERE, "meta_cache.json"), encoding="utf-8"))
bpm = json.load(open(os.path.join(HERE, "bpm_cache.json"), encoding="utf-8"))
SNIP = open(os.path.join(HERE, "marks_snippet.html"), encoding="utf-8").read()

# n de la lista -> (riesgo, por qué)
R = {
 # ---- QUEMADO: confirmado o casi seguro ya exprimido
 2583:("quemado","CONFIRMADO por vos: 52 samples en WhoSampled. Lo usaron Westside Gunn, MIKE, Ta-Ku, Jay Worthy y Drake. Sáquenlo."),
 2585:("quemado","Mismo disco que el anterior ('Inner Spectrum', Atlantic 1974). Si el A ya está exprimido, este lo está o lo va a estar."),
 686:("quemado","Brief Encounter es uno de los santos griales del sweet soul: reeditado y rastrillado por todos los diggers de soul."),
 997:("quemado","Carrie Cleveland está reeditada por Kalita Records. Su disco es de los más conocidos del private press soul."),
 746:("quemado","'Love Jones' de The Brighter Side of Darkness fue un hit de Billboard en el 73. Nada oculto."),
 4978:("quemado","Ryo Fukui ('Scenery') es el disco de jazz japonés más famoso de la reedición. Imposible que esté virgen."),
 4955:("quemado","Tohru Aizawa Quartet está reeditado por BBE con bombos y platillos. Es culto pero MUY conocido."),
 4858:("quemado","Hiroshi Sato es el productor canónico del city pop. 'Awakening' se reeditó varias veces."),
 4931:("quemado","El disco de Takako Mamiya ('Love Trip') es de los más caros y buscados del city pop."),
 # ---- MUY CONOCIDO en el circuito: verificá antes de usar
 2649:("conocido","Black Ivory es Leroy Burgess: el circuito del boogie/sweet soul de Harlem lo tiene rastrillado."),
 699:("conocido","Skip Mahoney & The Casuals son referencia del sweet soul de DC. Muy buscado."),
 709:("conocido","Tyrone Ashley viene del círculo de Funkadelic/Parliament; su disco se reeditó."),
 2571:("conocido","Banks & Hampton produjeron medio Memphis (Randy Brown, Shirley Brown). Nombre grande."),
 2622:("conocido","Brandi Wells es nombre conocido del modern soul/boogie (WMOT)."),
 257:("conocido","Debbie Taylor tiene reediciones y es conocida entre diggers de deep soul."),
 320:("conocido","David Oliver (Mercury) circula bastante en el modern soul."),
 4992:("conocido","Tomoko Aran: 'Midnight Pretenders' lo sampleó Tyler, the Creator. Ella entera quedó expuesta."),
 5122:("conocido","Tomoko Aran otra vez — mismo problema."),
 5032:("conocido","Hitomi Tohyama es de las voces más reeditadas del city pop."),
 5012:("conocido","Makoto Matsushita ('First Light') es disco de referencia del AOR japonés."),
 5025:("conocido","Kimiko Kasai grabó con Herbie Hancock. Nombre grande."),
 5130:("conocido","Yasuko Agawa es muy conocida en el city pop/jazz japonés."),
 4964:("conocido","Yuji Ohno (Lupin III) es de lo más sampleado del jazz japonés."),
 4961:("conocido","Yuji Ohno otra vez."),
 5350:("conocido","Hiromasa Suzuki tiene varias reediciones recientes."),
 5522:("conocido","Olli Ahvenlahti está reeditado; 'The Poet' circula mucho entre diggers."),
 5523:("conocido","Mismo disco que el anterior."),
 5502:("conocido","Perigeo es el grupo de fusion italiana más conocido."),
 5514:("conocido","Harold Mabern es jazz de catálogo conocido (Prestige)."),
 227:("conocido","The Montgomery Express se reeditó; circula en compilaciones de private press."),
 # ---- el resto: probablemente virgen (sello chico, sin reedición conocida)
}
VIRGEN = ("virgen", "No me consta reedición ni circulación en el circuito. Es de las que valen la verificación.")
ORD = {"quemado": 0, "conocido": 1, "virgen": 2}
ET = {"quemado": "🔴 Quemado", "conocido": "🟡 Conocido en el circuito", "virgen": "🟢 Probablemente virgen"}

fuego = [s for s in sel if s["tier"] == "fuego"]
for s in fuego:
    s["riesgo"], s["motivo"] = R.get(s["n"], VIRGEN)
fuego.sort(key=lambda s: (ORD[s["riesgo"]], s["playlist"]))

def vs(v): return "?" if v is None else (f"{v/1e6:.1f}M" if v >= 1e6 else f"{v//1000}k" if v >= 1000 else str(v))
def tempo(b):
    if not b: return "?"
    return f"{round(b/2)}" if b > 115 and 55 <= b/2 <= 115 else f"{round(b)}"
CSS = """body{font-family:system-ui,sans-serif;max-width:1020px;margin:24px auto;padding:0 16px;background:#f4efe6;color:#2a2420}
h1{font-size:1.4rem}h2{font-size:1.05rem;margin-top:2.2rem;border-bottom:2px solid #c9b8a0;padding-bottom:4px}
table{width:100%;border-collapse:collapse}td{padding:6px 8px;border-bottom:1px solid #e0d6c4;vertical-align:top;font-size:.92rem}
td.n{color:#8a7a66;width:2.4em;text-align:right}td.m{width:9.5em;color:#6b5d4d;font-size:.84rem;white-space:nowrap}
a{color:#8b2f1f;text-decoration:none;font-weight:600}a:hover{text-decoration:underline}
.ch{color:#6b5d4d;font-size:.82rem}.why{color:#4a4038;font-size:.86rem;margin-top:2px}
.nota{background:#efe6d2;border:1px solid #c9b8a0;padding:10px 14px;border-radius:6px;margin:12px 0;font-size:.9rem}
.ws{font-size:.78rem;margin-left:8px;color:#6b5d4d}"""
out = [f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Revisión · ¿ya está sampleado?</title><style>{CSS}</style></head><body>',
 '<h1>Revisión de los 66 🔥: ¿ya está quemado?</h1>',
 '<div class="nota">Tenías razón con Ace Spectrum: yo estaba midiendo <b>views del video</b>, que es obscuridad del upload, '
 'cuando lo que importa es <b>cuántos ya lo samplearon</b>, que es obscuridad de la obra. Varios de mis 🔥 tienen 250 views '
 'pero son famosos <i>dentro</i> del circuito de diggers.<br><br>'
 'Esta revisión es <b>mi criterio musical, no una consulta a WhoSampled</b> (ver abajo por qué). Tomala como '
 '"verificá esto antes de perder tiempo", no como veredicto. Cada fila tiene un link directo a la búsqueda en WhoSampled '
 'para que lo confirmes vos en un click.<br><br>'
 'Este archivo es nuevo: <b>no toqué ninguna de las 5 listas que estás usando</b>.</div>']
for r in ["quemado", "conocido", "virgen"]:
    grupo = [s for s in fuego if s["riesgo"] == r]
    out.append(f'<h2>{ET[r]} ({len(grupo)})</h2><table>')
    for i, s in enumerate(grupo, 1):
        vid = s["id"]; m = meta.get(vid, {}); b = bpm.get(vid, {})
        q = s["title"].split(" - ")[0][:40] + " " + (s["title"].split(" - ")[1][:40] if " - " in s["title"] else "")
        ws = "https://www.whosampled.com/search/?q=" + html.escape(q.replace(" ", "+"))
        info = f'{m.get("year") or "?"}<br>{tempo(b.get("bpm"))} BPM · {b.get("key","?")}<br>{vs(m.get("views") or s.get("views"))} views'
        out.append(f'<tr><td class="n">{i}</td><td><a href="https://www.youtube.com/watch?v={vid}" target="_blank">{html.escape(s["title"][:88])}</a>'
                   f'<a class="ws" href="{ws}" target="_blank">[WhoSampled ↗]</a>'
                   f'<div class="ch">{html.escape(s["uploader"])} · {s["playlist"]}</div>'
                   f'<div class="why">{html.escape(s["motivo"])}</div></td><td class="m">{info}</td></tr>')
    out.append("</table>")
out.append(SNIP + "</body></html>")
open(OUT, "w", encoding="utf-8").write("\n".join(out))
from collections import Counter
print(Counter(s["riesgo"] for s in fuego), "→", OUT)
