# -*- coding: utf-8 -*-
"""Cruza las vetas que surgen de WhoSampled (qué escuelas cavan los productores
que a Thomas le gustan) contra los pools que ya tengo listados."""
import json, os, re
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))

pool = {}
for f in ("vetas_pool.json", "latam_pool.json"):
    p = os.path.join(HERE, f)
    if os.path.exists(p):
        d = json.load(open(p, encoding="utf-8"))
        for k, v in d.items():
            pool.setdefault(k, v)
print(f"pool total: {len(pool)}")

# Las vetas, sacadas de lo que REALMENTE samplean Daringer, Conductor, Craven,
# Knxwledge, Camoflauge Monk y Alchemist. Cada una con sus marcadores.
VETAS = {
 "library_europea": [r"\blibrary\b", r"\bKPM\b", r"de ?wolfe", r"\bbruton\b", r"sonoton",
   r"selected sound", r"chappell", r"\bcoloursound\b", r"\bconroy\b", r"john fiddy",
   r"marchetti", r"de roubaix", r"colombier", r"lesiman", r"piero umiliani",
   r"alessandro alessandroni", r"nicolai", r"\bortolani\b", r"\btrovajoli\b",
   r"\bferrio\b", r"stelvio", r"\bcipriani\b", r"\bfabor\b", r"\breverberi\b"],
 "este_europa":    [r"sosnicka", r"\bzodiac\b", r"manukjan", r"\bpolski\b", r"polskie",
   r"\bmelodia\b", r"мелодия", r"supraphon", r"\bpepita\b", r"\bbalkanton\b",
   r"\bjugoton\b", r"\bopus\b.*\b19[67]\d", r"czechoslovak", r"hungarian", r"yugoslav"],
 "jazz_euro":      [r"jarrett", r"garbarek", r"\bECM\b", r"stan tracey", r"ian carr",
   r"\bnucleus\b", r"greenslade", r"cunimondo", r"\bMPS\b", r"\bSABA\b", r"black saint",
   r"\bsteeplechase\b", r"\benja\b"],
 "sweet_soul":     [r"faith,? hope", r"stairsteps", r"zingara", r"sound experience",
   r"honey cone", r"the futures", r"rance allen", r"diann franklin", r"gloria scott",
   r"prince harold", r"odyssey 5", r"jorge dalto", r"ahmad jamal", r"eugene record",
   r"van mccoy", r"lamont dozier"],
 "gospel_privado": [r"\bgospel\b", r"lemon singers", r"\bsingers\b", r"\bchoir\b",
   r"\bministries\b", r"\btabernacle\b", r"church of", r"\bdisciples\b", r"\bcrusaders?\b.*gospel"],
 "psych_mundial":  [r"cem karaca", r"far east family", r"svika pick", r"\banadolu\b",
   r"\bturkish\b", r"\bpersian\b", r"\biranian\b", r"\bethiopian\b", r"\bgreek\b.*\b19[67]\d"],
}
RX = {k: re.compile("|".join(v), re.I) for k, v in VETAS.items()}

hits = {k: [] for k in VETAS}
for vid, e in pool.items():
    t = e.get("title") or ""
    u = e.get("uploader") or ""
    blob = t + " || " + u
    for k, rx in RX.items():
        if rx.search(blob):
            hits[k].append({"id": vid, "title": t, "uploader": u,
                            "dur": e.get("dur"), "views": e.get("views")})

print("\n=== lo que YA tengo listado, por veta ===")
for k, v in hits.items():
    print(f"{k:18} {len(v):4}  canales: {[c for c,_ in Counter(x['uploader'] for x in v).most_common(4)]}")
json.dump(hits, open(os.path.join(HERE, "ws_hits.json"), "w", encoding="utf-8"), ensure_ascii=False)

print("\n=== muestra de las vetas flacas (lo que hay que salir a buscar) ===")
for k in ("library_europea", "este_europa", "jazz_euro", "psych_mundial"):
    for x in hits[k][:6]:
        print(f"  [{k}] {x['title'][:72]} | {x['uploader'][:26]}")
