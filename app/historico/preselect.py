"""Preselección sobre los 7.942 de canales curadores, con todo lo que sabemos del oído de Thomas.
No decide: ordena. Los finalistas se miden con el DSP (tonalidad + tempo) y ahí sí se filtra."""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
pool = json.load(open(os.path.join(HERE, "vetas_pool.json"), encoding="utf-8"))
rows = set(json.load(open(os.path.join(HERE, "vetas_rows.json"))))

# hit rate medido en el benchmark (guardados / en pool)
# (guardados, vistos) medidos en el benchmark; se suavizan con un prior para que 2/2 no valga 100%
CRUDO = {"si":(3,3),"Winta Groove":(2,2),"TheRAREGROOVEMAN":(3,13),"Music for empty rooms":(6,41),
 "Soultwinz":(2,16),"skeenery":(1,11),"Rare Samples & Songs Oleg Tsoy":(4,44),"Neglected Trax":(1,8),
 "Casen Fike":(1,5),"JazzManDean":(1,5),"ants kask":(1,3),"foreal":(1,3),"Krem Soulz":(1,2),
 "secondscene":(1,2),"aaappleknocker":(1,3),"mikeejaylovessoul":(1,4),"Athens of The North":(1,1),
 "Cool Breeze":(1,2),"On the Rocks Records":(1,1),"The Voice of Anton":(1,6),"Elwood P. Dowd":(1,1),
 "JefferyBeats":(1,1),"BigPeter1027 Real Music Channel":(1,1),"DJ Vinyl Goblin":(1,1),
 "Five Special Records":(1,1),"Vinyle Archéologie":(1,10),"Dusty Breaks":(1,10)}
BASE, ALFA = 0.055, 12.0
CANAL = {k: (g + ALFA * BASE) / (n + ALFA) for k, (g, n) in CRUDO.items()}

# palabras que anuncian balada / lento / atmósfera (lo que él guarda)
LENTO = re.compile(r"\b(love|lover|loving|rain|rainy|night|nite|lonely|alone|dream|dreaming|tears|cry|"
 r"cryin|sad|blue|blues|slow|ballad|theme|mood|soft|quiet|morning|sunrise|sunset|heart|"
 r"heartache|miss|missing|goodbye|farewell|without|memory|memories|remember|forever|"
 r"always|tender|gentle|sweet|smile|angel|star|moon|sky|sea|ocean|wind|autumn|winter|"
 r"silence|silent|waltz|lament|lamento|nostalgia|saudade|triste|amor|noche|lluvia|"
 r"balada|tema|recuerdo|canci[óo]n|elegy|prayer|hymn|interlude|reverie|romance|romantic|"
 r"serenade|whisper|shadow|mist|fog|velvet|silk|smooth|mellow|warm|peace|still)\b", re.I)
# palabras que anuncian rápido / efusivo / festivo (lo que descarta)
RAPIDO = re.compile(r"\b(disco|dance|dancin|party|boogie|shake|jam|funky|funk|get down|"
 r"stomp|shuffle|hustle|rock ?n ?roll|twist|groove it|move|movin|jump|jumpin|"
 r"carnaval|carnival|samba|guaguanc[óo]|descarga|mambo|cha ?cha|merengue|cumbia|"
 r"celebration|fiesta|hot|fire|burn|crazy|wild|freak|freaky|bump|humpin|"
 r"workout|work it|do it|shout|holler|scream)\b", re.I)
# ruido duro
RUIDO = re.compile(r"karaoke|tutorial|instrumental version|backing track|cover by|reaction|"
 r"full album|album completo|mix\b|megamix|dj set|type beat|sample pack|interview|"
 r"entrevista|documental|live at|en vivo|directo \d|remix|edit\b", re.I)
# el canal "Music for empty rooms" declara país, género y año en el título
MFER = re.compile(r"\[([^\]]+)\]\s*([^(]+)\((\d{4})\)")
GEN_OK = re.compile(r"soul|jazz|easy listening|downtempo|citypop|city pop|balear|ambient|"
 r"lo-?fi|score|library|fusion|mpb|bossa|psych soul|gospel", re.I)
GEN_NO = re.compile(r"\bdisco\b|\bfunk\b|boogie|rock|punk|metal|new wave|house|techno|reggae|ska|"
 r"garage|surf|country|blues rock", re.I)

def anio_de(t):
    m = re.search(r"\b(19[4-9]\d|20[0-2]\d)\b", t)
    return int(m.group(1)) if m else None

out = []
for vid, e in pool.items():
    if vid not in rows: continue
    t, u, d, v = e["title"], e["uploader"], e["dur"] or 0, e["views"]
    if RUIDO.search(t): continue
    s = 0.0
    s += 2.6 * CANAL.get(u, 0.08)                       # el canal que ya le rindió
    if LENTO.search(t): s += 1.0
    if RAPIDO.search(t): s -= 1.2
    if 170 <= d <= 450: s += 0.7                        # 2:50–7:30, donde cae lo que guarda
    elif 450 < d <= 620: s += 0.3
    elif d < 140: s -= 0.6
    if v is not None:                                   # obscuridad: castiga mainstream, no premia 200 views
        if v > 600_000: s -= 1.4
        elif v > 150_000: s -= 0.5
        elif 1_500 <= v <= 80_000: s += 0.5
        elif v < 300: s -= 0.3
    a = anio_de(t)
    if a and 1968 <= a <= 1988: s += 0.6
    elif a and (a < 1962 or a > 1996): s -= 0.7
    m = MFER.search(t)
    if m:
        pais, gen = m.group(1), m.group(2)
        if GEN_OK.search(gen): s += 0.9
        if GEN_NO.search(gen): s -= 0.9
        if re.search(r"japan|brazil|usa|us\b|italy|france", pais, re.I): s += 0.25
    if re.search(r"- ?topic$", u, re.I): s += 0.2        # Topic = metadata de distribuidor
    out.append({"id": vid, "score": round(s, 2), "title": t, "uploader": u, "dur": d, "views": v, "anio": a})

out.sort(key=lambda x: -x["score"])
TOP, CUPO = 900, 70
sel, por_canal = [], {}
for x in out:
    c = por_canal.get(x["uploader"], 0)
    if c >= CUPO: continue
    por_canal[x["uploader"]] = c + 1
    sel.append(x)
    if len(sel) >= TOP: break
json.dump(sel, open(os.path.join(HERE, "preselect.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
open(os.path.join(HERE, "preselect_ids.txt"), "w").write(" ".join(x["id"] for x in sel))
from collections import Counter
print(f"{len(out)} evaluados → top {len(sel)} | corte en score {sel[-1]['score']}")
print("por canal:", Counter(x["uploader"] for x in sel).most_common(12))
