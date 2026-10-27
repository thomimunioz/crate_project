# -*- coding: utf-8 -*-
"""Valida oido.py contra el feedback real exportado el 24-oct-2026.
Si el modulo no separa lo guardado de lo rechazado, no sirve."""
import json, glob, os, sys
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from oido import loopeabilidad, curva_views, pais_de

sel = {x["id"]: x for x in json.load(open(os.path.join(HERE, "seleccion.json"), encoding="utf-8"))}
meta = json.load(open(os.path.join(HERE, "meta_cache.json"), encoding="utf-8"))
bpm = json.load(open(os.path.join(HERE, "bpm_cache.json"), encoding="utf-8"))

A, R = [], []
for f in glob.glob(r"C:\Users\thomi\Downloads\crate-feedback-*.json"):
    for t in json.load(open(f, encoding="utf-8"))["temas"]:
        if t.get("agregado"): A.append(t)
        elif t.get("motivo"): R.append(t)

def puntuar(t):
    vid = t["id"]
    s = sel.get(vid, {})
    m = meta.get(vid, {})
    b = bpm.get(vid, {})
    tit = t["titulo"]
    dur = s.get("dur") or b.get("dur")
    v = m.get("views") if m.get("views") is not None else s.get("views")
    pts = loopeabilidad(tit, dur) + curva_views(v)
    bb = b.get("bpm")
    if bb:
        bb = bb / 2 if bb > 115 and 55 <= bb / 2 <= 115 else bb
        if 62 <= bb <= 95: pts += 1.0
        elif bb > 108: pts -= 0.8
    if "minor" in (b.get("key") or ""): pts += 0.5
    return pts, pais_de(tit), dur, v

pa = [puntuar(t) for t in A]
pr = [puntuar(t) for t in R]
ma = sum(x[0] for x in pa) / len(pa)
mr = sum(x[0] for x in pr) / len(pr)
print("GUARDADOS  n=%2d  score medio %+.2f" % (len(pa), ma))
print("RECHAZADOS n=%2d  score medio %+.2f" % (len(pr), mr))
print("separacion: %+.2f" % (ma - mr))

# AUC: probabilidad de que un guardado puntue mas alto que un rechazado
pares = gana = 0
for a, _, _, _ in pa:
    for r, _, _, _ in pr:
        pares += 1
        gana += 1 if a > r else (0.5 if a == r else 0)
print("AUC = %.3f  (0.5 = al azar)" % (gana / pares))

print("\n--- los rechazados que el modulo MAS castiga (deberian ser los peores) ---")
for (p, pais, d, v), t in sorted(zip(pr, R), key=lambda z: z[0][0])[:7]:
    print("  %+.1f  %-10s %s" % (p, t["motivo"], t["titulo"][:58]))
print("\n--- guardados que el modulo castiga (falsos negativos: lo que se nos escapa) ---")
for (p, pais, d, v), t in sorted(zip(pa, A), key=lambda z: z[0][0])[:6]:
    print("  %+.1f  %s" % (p, t["titulo"][:62]))
