# -*- coding: utf-8 -*-
"""Saca los artistas/compositores de las vetas nuevas, filtrando lo que Thomas YA vio.
La verificación en WhoSampled se hace por ARTISTA, no por tema: si el tipo tiene
200 samples está quemado entero; si tiene 2, toda su obra sigue virgen."""
import json, os, re
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
hits = json.load(open(os.path.join(HERE, "ws_hits.json"), encoding="utf-8"))

# todo lo que ya se le mostró o ya estaba en sus playlists
vistos = set()
for f in ("seleccion.json", "fuego.json", "latam_short.json"):
    p = os.path.join(HERE, f)
    if os.path.exists(p):
        d = json.load(open(p, encoding="utf-8"))
        for x in (d if isinstance(d, list) else d.values()):
            if isinstance(x, dict) and x.get("id"): vistos.add(x["id"])
for f in ("sel_ids.txt", "latam_ids.txt", "sierra_ids.txt", "preselect_ids.txt"):
    p = os.path.join(HERE, f)
    if os.path.exists(p): vistos.update(open(p).read().split())
print(f"ya vistos/entregados: {len(vistos)}")

VETAS_NUEVAS = ("library_europea", "este_europa", "jazz_euro", "psych_mundial")
RUIDO = re.compile(r"karaoke|tutorial|full album|mix\b|megamix|dj set|type beat|"
                   r"sample pack|reaction|live at|documental", re.I)

def artista_de(t):
    """El artista es lo de antes del primer ' - '. Limpia prefijos de canal."""
    t = re.sub(r"^\s*\[[^\]]*\]\s*", "", t)
    a = re.split(r"\s+[-–—]\s+|\s*:\s*", t, 1)[0]
    a = re.sub(r"\s*\([^)]*\)\s*$", "", a).strip(" .,·|")
    return a if 2 < len(a) < 48 else None

cands, por_artista = [], {}
for k in VETAS_NUEVAS:
    for x in hits[k]:
        if x["id"] in vistos: continue
        d = x.get("dur") or 0
        if d and (d < 95 or d > 900): continue       # 1:35 a 15:00
        if RUIDO.search(x["title"]): continue
        a = artista_de(x["title"])
        if not a: continue
        x["veta"], x["artista"] = k, a
        cands.append(x)
        por_artista.setdefault(a, []).append(x)

print(f"candidatos nuevos (no vistos, duración sana): {len(cands)}")
print(f"artistas distintos: {len(por_artista)}\n")
rank = sorted(por_artista.items(), key=lambda kv: -len(kv[1]))
print("=== artistas con más material en el pool (a verificar en WhoSampled) ===")
for a, xs in rank[:28]:
    vt = Counter(x["veta"] for x in xs).most_common(1)[0][0]
    print(f"  {len(xs):3}  {a[:44]:44} [{vt}]")
json.dump({"cands": cands, "rank": [[a, len(xs)] for a, xs in rank]},
          open(os.path.join(HERE, "ws_cands.json"), "w", encoding="utf-8"), ensure_ascii=False)
