# -*- coding: utf-8 -*-
"""Arma el crate.html unificado con las tandas vigentes."""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from crate_html import Tanda, generar

bpm = json.load(open(os.path.join(HERE, "bpm_cache.json"), encoding="utf-8"))
plegar = lambda b: b / 2 if b > 115 and 55 <= b / 2 <= 115 else b

# --- instrumentales: mismo criterio que instrumentales.html ---
def tipo(t):
    if re.search(r"\bdub\b", t, re.I): return "dub"
    if re.search(r"off ?vocal", t, re.I): return "off vocal"
    if re.search(r"backing track|minus one|playback", t, re.I): return "backing"
    return "instrumental"
POR = {"dub": "Dub: la voz entra y sale, el resto es base pelada",
       "off vocal": "Off vocal: la cara B instrumental del single japonés",
       "backing": "Pista de acompañamiento, sin voz por definición",
       "instrumental": "Instrumental del propio disco, no un karaoke moderno"}
inst = []
for x in json.load(open(os.path.join(HERE, "inst_pre.json"), encoding="utf-8")):
    b = bpm.get(x["id"], {}).get("bpm")
    if not b or plegar(b) > 112: continue
    x["why"] = POR[tipo(x["title"])]
    x["_k"] = (0 if "minor" in (bpm[x["id"]].get("key") or "") else 1, plegar(b))
    inst.append(x)
inst.sort(key=lambda y: y["_k"]); inst = inst[:40]

# --- demo: 50, por genero ---
demo = []
GN = {"rnb": "R&B", "80s": "80s", "soul": "Soul", "citypop": "City Pop", "fusion": "Fusion"}
for g, v in json.load(open(os.path.join(HERE, "demo_final.json"), encoding="utf-8")).items():
    for x in v:
        x["why"] = "[%s] %s" % (GN.get(g, g), x.get("why", ""))
        demo.append(x)

# --- soul pendiente: 79, fuego primero ---
r = json.load(open(os.path.join(HERE, "repaso.json"), encoding="utf-8"))
orden = {"fuego": 0, "bien": 1, "quizas": 2}
soul = sorted(r["queda"], key=lambda x: (orden.get(x.get("tier"), 3), -x.get("p", 0)))

T = [
 Tanda("instrumentales", "Instrumentales",
       "<b>40 temas sin una sola voz.</b> Salieron de barrer las 50.900 del pool buscando "
       "cómo un disco de época declara que no trae voz: instrumental, dub, off vocal, "
       "backing track. 80% en tonalidad menor, mediana 70 BPM. "
       "Un instrumental no tiene <i>un hueco</i>: es todo hueco.", inst),
 Tanda("demo", "Demo · 10 por género",
       "<b>50 temas, 10 de cada género</b>, elegidos a mano. En fusion hay Bahrein, Líbano, "
       "Austria, Canadá y Francia: era el reclamo de que todo fuera USA y Japón. "
       "Mediana 66 BPM, 74% en menor.", demo),
 Tanda("soul", "Soul pendiente",
       "<b>79 de la lista de SOUL que no abriste</b>, con los 🔥 primero (58% de acierto "
       "contra 38% de los 👍). Vienen de 4 canales de los que no tengo ningún dato tuyo: "
       "Casen Fike, DJ Vinyl Goblin, Krem Soulz y Soultwinz. "
       "Marcando pocos de cada uno quedan medidos y la próxima se puede filtrar en serio.", soul),
]
n = generar(T, r"G:\Thomi - Mi Carpeta\crate_project\crate.html")
for t in T:
    print("  %-16s %3d" % (t.slug, len(t.items)))
print("total %d -> crate.html" % n)
