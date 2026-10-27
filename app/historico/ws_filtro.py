# -*- coding: utf-8 -*-
"""De los 937 hermanos: saca lo ya visto, la basura, y sobre todo EL CORTE QUE
YA FUE SAMPLEADO (ese está quemado por definición). Deja los hermanos vírgenes."""
import json, os, re, unicodedata
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(os.path.join(HERE, "ws_semillas.json"), encoding="utf-8"))

def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower())

# el tema que cada productor YA usó: ese sale
QUEMADO = {
 "Faith Hope & Charity":["keep me baby"], "Zingara":["loves calling"],
 "Sound Experience":["you dont know what youre doing"], "The Raes":["to love somebody"],
 "The Futures":["deep inside of me"], "Miquel Brown":["do it"],
 "Diann Franklin":["hes there"], "Gloria Scott":["i just couldnt take a goodbye"],
 "Prince Harold":["forget about me"], "Odyssey 5":["peace of mind"],
 "Jorge Dalto":["for openers"], "Wendy Saddington":["i think of you"],
 "Monk Higgins":["i believe to my soul","railroad"], "Derrick Erni":["never"],
 "Eugene Record":["when we pull the shades"], "Frank Cunimondo Trio":["love so fine"],
 "Sweet Thursday":["gilbert street"], "Lesiman":["sbarramento"],
 "John Fiddy":["baddy"], "Michel Colombier":["morning is come again"],
 "Thijs Van Leer":["street rondo"], "Howard Lemon Singers":["i know god is real"],
 "Gianni Marchetti":["february"], "Francois de Roubaix":["les dunes dostende"],
 "Zdzislawa Sosnicka":["dobranocka"], "Stan Tracey":["starless and bible black"],
 "Ian Carr Nucleus":["remadione"], "Dave Greenslade":["dry land"],
 "Sergei Manukjan":["looking for you"], "Svika Pick":["false stars"],
 "Cem Karaca":["sevdan beni"], "Riff Raff":["havakak"],
}
vistos = set()
for f in ("sel_ids.txt","latam_ids.txt","sierra_ids.txt","preselect_ids.txt"):
    p = os.path.join(HERE, f)
    if os.path.exists(p): vistos.update(open(p).read().split())
for f in ("seleccion.json","fuego.json"):
    p = os.path.join(HERE, f)
    if os.path.exists(p):
        d = json.load(open(p, encoding="utf-8"))
        for x in (d if isinstance(d, list) else d.values()):
            if isinstance(x, dict) and x.get("id"): vistos.add(x["id"])

BASURA = re.compile(r"karaoke|tutorial|type beat|sample pack|reaction|how to|lyric|"
                    r"\bmix\b|megamix|dj set|interview|entrevista|documental|"
                    r"\blive\b|en vivo|cover by|remix|\bedit\b|topic.*playlist", re.I)
# efusivo / rápido: lo que Thomas descarta
RAPIDO = re.compile(r"\b(disco|dance|party|boogie|shake|funky|get down|stomp|hustle|"
                    r"rock ?n ?roll|twist|jump|celebration|fiesta|hot|fire|crazy|wild|"
                    r"freak|bump|shout|workout|do it|move|movin)\b", re.I)
LENTO = re.compile(r"\b(love|rain|night|lonely|alone|dream|tears|cry|sad|blue|slow|"
                   r"ballad|theme|mood|soft|quiet|morning|heart|miss|goodbye|memory|"
                   r"remember|forever|tender|gentle|sweet|angel|star|moon|sky|sea|wind|"
                   r"autumn|silence|waltz|lament|nostalgia|elegy|prayer|interlude|"
                   r"reverie|romance|serenade|whisper|shadow|mist|velvet|smooth|mellow|"
                   r"warm|peace|still|adagio|nocturne|ninna|notte|amore|piano)\b", re.I)

out, desc = [], Counter()
for vid, e in S.items():
    t, sem = e["title"], e["semilla"]
    nt, ns = norm(t), norm(sem)
    if vid in vistos: desc["ya visto"] += 1; continue
    d = e.get("dur") or 0
    if not d or d < 95 or d > 900: desc["duracion"] += 1; continue
    if BASURA.search(t): desc["basura"] += 1; continue
    # el resultado tiene que ser realmente del artista semilla
    if not all(w in nt for w in ns.split() if len(w) > 3): desc["no es el artista"] += 1; continue
    if any(q in nt for q in QUEMADO.get(sem, [])): desc["EL CORTE YA SAMPLEADO"] += 1; continue
    s = 0.0
    if LENTO.search(t): s += 1.0
    if RAPIDO.search(t): s -= 1.2
    v = e.get("views")
    if v is not None:
        if v > 600_000: s -= 1.6
        elif v > 150_000: s -= 0.6
        elif 1_000 <= v <= 60_000: s += 0.6
        elif v < 200: s -= 0.2
    if 170 <= d <= 450: s += 0.7
    elif d < 140: s -= 0.5
    e.update({"id": vid, "score": round(s, 2)})
    out.append(e)

out.sort(key=lambda x: -x["score"])
print("descartes:", dict(desc))
print(f"\nhermanos vírgenes que quedan: {len(out)}")
print("por escuela:", dict(Counter(x["escuela"] for x in out)))
json.dump(out, open(os.path.join(HERE, "ws_hermanos.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("\n=== top 20 ===")
for x in out[:20]:
    v = x.get("views"); vs = "?" if v is None else (f"{v//1000}k" if v>=1000 else str(v))
    print(f"  {x['score']:+.1f}  {x['title'][:66]:66} | {vs:>6} | {x['quien']}")
