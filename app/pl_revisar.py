# -*- coding: utf-8 -*-
"""Revisa las 5 listas de Thomas buscando temas en la lista equivocada.
Ahora con el anio real (℗ de la descripcion del Topic, o del titulo)."""
import json, os, re
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(os.path.join(HERE, "pl_pool.json"), encoding="utf-8"))
META = json.load(open(os.path.join(HERE, "meta_cache.json"), encoding="utf-8"))

NOMBRE = {"80s": "80s (quiet storm 84-92)", "soul": "SOUL (70s)",
          "rnb": "R&B SOUL (77-92)", "citypop": "CITY POP (jp 76-88)",
          "fusion": "JAZZ FUSION (74-90)"}
RANGO = {"80s": (1983, 1993), "soul": (1965, 1984), "rnb": (1976, 1993),
         "citypop": (1975, 1989), "fusion": (1972, 1992)}

JP = re.compile(r"[぀-ヿ一-鿿]")
JP_LAT = re.compile(
    r"\b(yamashita|ohashi|kubota|yoshida|iwasaki|kadomatsu|omega ?tribe|anri|"
    r"takeuchi|matsubara|ohno|sugiyama|murata|hosono|sakamoto|nanjo|yano|"
    r"minako|mariya|taeko|junko|akiko|toshiki|tatsuro|casiopea|t-?square|"
    r"naniwa|piper|hi-?fi ?set|momoko|rajie|hiroshi sato|masayoshi|"
    r"kimiko|yasuko|tomoko|miki matsubara|eri ohno)\b", re.I)
BR = re.compile(r"\b(brasil|brazil|\bmpb\b|bossa|milton nascimento|djavan|jobim|"
                r"caetano|marcos valle|azymuth|ivan lins|joyce|elis regina|tim maia|"
                r"sergio mendes|deodato|gal costa|edu lobo|hyldon|cassiano)\b", re.I)
AR = re.compile(r"\b(spinetta|jade|charly garcia|seru|invisible|pastoral|"
                r"arco iris|pedro aznar|dino saluzzi|litto nebbia|alas)\b", re.I)
FUSION_W = re.compile(r"\b(fusion|lonnie liston|sadao|watanabe|casiopea|"
                      r"weather report|return to forever|crusaders|bob james|"
                      r"grover washington|ronnie laws|roy ayers|george duke|"
                      r"herbie hancock|headhunters|jazz ?funk|azymuth)\b", re.I)

def anio(vid, tit):
    y = META.get(vid, {}).get("year")
    if y and str(y).isdigit():
        return int(y), META.get(vid, {}).get("phonogram", False)
    m = re.search(r"\b(19[5-9]\d|200\d)\b", tit)
    return (int(m.group(1)), False) if m else (None, False)

def escena(tit):
    if JP.search(tit) or JP_LAT.search(tit): return "japon"
    if BR.search(tit): return "brasil"
    if AR.search(tit): return "argentina"
    return None

por_lista = defaultdict(list)
for vid, e in P.items():
    e["id"] = vid
    e["anio"], e["phono"] = anio(vid, e["title"])
    e["escena"] = escena(e["title"])
    for L in e["listas"]:
        por_lista[L].append(e)

print("=" * 76)
print("ESTADO DE LAS 5 LISTAS")
print("=" * 76)
for k in ("80s", "soul", "rnb", "citypop", "fusion"):
    it = por_lista[k]
    ys = sorted(x["anio"] for x in it if x["anio"])
    esc = Counter(x["escena"] for x in it if x["escena"])
    print("%-26s %3d | anio %3d/%3d | mediana %s | p10-p90 %s-%s | %s" % (
        NOMBRE[k], len(it), len(ys), len(it),
        ys[len(ys) // 2] if ys else "?",
        ys[len(ys) // 10] if ys else "?", ys[-max(1, len(ys) // 10)] if ys else "?",
        dict(esc) or "-"))

print()
print("=" * 76)
print("A REVISAR")
print("=" * 76)
hall = []
for k, it in por_lista.items():
    lo, hi = RANGO[k]
    for x in it:
        mot = []
        y = x["anio"]
        if y and not (lo <= y <= hi):
            d = (lo - y) if y < lo else (y - hi)
            if d >= 3:                      # 1-2 anios de margen no es error
                mot.append("%d (la lista es %d-%d)" % (y, lo, hi))
        if k == "citypop" and x["escena"] and x["escena"] != "japon":
            mot.append("no es japones: es %s" % x["escena"])
        if k in ("80s", "rnb", "soul") and FUSION_W.search(x["title"]):
            mot.append("es fusion, no %s" % k)
        if k in ("80s", "rnb", "soul") and x["escena"] == "japon":
            mot.append("japones en %s: va a CITY POP?" % k)
        if len(x["listas"]) > 1:
            mot.append("tambien esta en: %s" % ", ".join(c for c in x["listas"] if c != k))
        if mot:
            hall.append((k, x, mot))

vistos = set()
for k in ("80s", "soul", "rnb", "citypop", "fusion"):
    g = [h for h in hall if h[0] == k]
    if not g: continue
    print("\n--- %s: %d a revisar de %d ---" % (NOMBRE[k], len(g), len(por_lista[k])))
    for _, x, mot in sorted(g, key=lambda h: h[1]["anio"] or 9999):
        mark = " P" if x["phono"] else "  "
        print("  %4s%s %s" % (x["anio"] or "?", mark, x["title"][:60]))
        print("         %s" % " | ".join(mot))
        vistos.add(x["id"])

json.dump([{"lista": k, "motivos": m, **x} for k, x, m in hall],
          open(os.path.join(HERE, "pl_revision.json"), "w", encoding="utf-8"),
          ensure_ascii=False)
print("\n%d temas a revisar, de %d" % (len(vistos), len(P)))
print("(P = anio del ℗ del distribuidor, no del titulo)")
