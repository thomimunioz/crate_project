# -*- coding: utf-8 -*-
"""Qué señal separa de verdad lo guardado de lo rechazado, sobre el feedback
real del 24-oct. Mide una por una en vez de suponer."""
import json, glob, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sel = {x["id"]: x for x in json.load(open(os.path.join(HERE, "seleccion.json"), encoding="utf-8"))}
meta = json.load(open(os.path.join(HERE, "meta_cache.json"), encoding="utf-8"))
bpm = json.load(open(os.path.join(HERE, "bpm_cache.json"), encoding="utf-8"))

A, R = [], []
for f in glob.glob(r"C:\Users\thomi\Downloads\crate-feedback-*.json"):
    for t in json.load(open(f, encoding="utf-8"))["temas"]:
        (A if t.get("agregado") else R if t.get("motivo") else []).append(t) \
            if (t.get("agregado") or t.get("motivo")) else None

def datos(t):
    vid = t["id"]
    s, m, b = sel.get(vid, {}), meta.get(vid, {}), bpm.get(vid, {})
    bb = b.get("bpm")
    if bb and bb > 115 and 55 <= bb / 2 <= 115:
        bb = bb / 2
    return {"dur": s.get("dur") or b.get("dur"),
            "views": m.get("views") if m.get("views") is not None else s.get("views"),
            "bpm": bb, "bpm_conf": b.get("bpm_conf"), "key_conf": b.get("key_conf"),
            "minor": 1 if "minor" in (b.get("key") or "") else 0,
            "year": m.get("year"), "tit": t["titulo"]}

da = [datos(t) for t in A]
dr = [datos(t) for t in R]

def auc(f):
    va = [f(x) for x in da]; vr = [f(x) for x in dr]
    va = [v for v in va if v is not None]; vr = [v for v in vr if v is not None]
    if not va or not vr: return None, 0, 0
    p = g = 0
    for a in va:
        for r in vr:
            p += 1; g += 1 if a > r else (0.5 if a == r else 0)
    return g / p, sum(va) / len(va), sum(vr) / len(vr)

SEN = {
 "duracion":        lambda x: x["dur"],
 "views":           lambda x: -(x["views"] or 0),
 "bpm":             lambda x: -(x["bpm"] or 0),
 "bpm_confianza":   lambda x: x["bpm_conf"],
 "key_confianza":   lambda x: x["key_conf"],
 "tonalidad_menor": lambda x: x["minor"],
 "anio":            lambda x: int(x["year"]) if str(x["year"] or "").isdigit() else None,
 "largo_titulo":    lambda x: len(x["tit"]),
}
print("senal              AUC    media(guardado)  media(rechazado)")
print("-" * 62)
for n, f in sorted(SEN.items(), key=lambda kv: -(auc(kv[1])[0] or 0)):
    a, ma, mr = auc(f)
    if a is None: continue
    marca = "  <<<" if abs(a - 0.5) > 0.12 else ""
    print("%-18s %.3f  %12.1f  %13.1f%s" % (n, a, ma, mr, marca))

print("\nbpm_conf de los que rechazo por jam/ritmo/bpm:")
for t, d in zip(R, dr):
    if t["motivo"] in ("bpm", "ritmo"):
        print("   %.2f  %s" % (d["bpm_conf"] or 0, t["titulo"][:56]))
print("bpm_conf de los japoneses que GUARDO:")
for t, d in zip(A, da):
    if any(c in t["titulo"] for c in "大宮雄坂"):
        print("   %.2f  %s" % (d["bpm_conf"] or 0, t["titulo"][:56]))
