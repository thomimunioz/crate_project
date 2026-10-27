# -*- coding: utf-8 -*-
"""Preselecciona candidatos por genero para la demo, con TODO lo corregido ayer:

  * views: neutral hasta 100k, warning hasta 300k, fuera arriba. Nunca premiar
    lo de pocas visitas (dos veces me marco "pifiaste x las vistas", y ademas
    los vinilos de 200 views suelen sonar mal).
  * nada de 6/8 ni valses: no loopea en 4/4 (me lo marco 3 veces).
  * nada de jazz ortodoxo / jam / trio de piano ("imposible samplear esto").
  * duracion: nada por debajo de 2:45, y premio a lo largo (mas chance de que
    haya un hueco instrumental).
  * dedup contra TODO lo que ya le mande alguna vez ("ya me lo has mandado en
    alguna otra tanda, ojo con esto").
"""
import json, os, re, unicodedata
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))

pool = {}
for f in ("demo_cavado.json", "fsr_nuevo.json", "ws_pool.json", "vetas_pool.json"):
    p = os.path.join(HERE, f)
    if os.path.exists(p):
        for k, v in json.load(open(p, encoding="utf-8")).items():
            if k not in pool:
                pool[k] = v
print("pool: %d" % len(pool))

# --- todo lo que ya vio o ya le mande, en cualquier tanda ---
vistos = set()
for f in ("sel_ids.txt", "latam_ids.txt", "sierra_ids.txt", "preselect_ids.txt",
          "ws_sel_ids.txt", "pl_ids.txt"):
    p = os.path.join(HERE, f)
    if os.path.exists(p):
        vistos.update(open(p).read().split())
for f in ("seleccion.json", "fuego.json", "ws_sel.json", "ws_finalistas.json"):
    p = os.path.join(HERE, f)
    if os.path.exists(p):
        d = json.load(open(p, encoding="utf-8"))
        for x in (d if isinstance(d, list) else d.values()):
            if isinstance(x, dict) and x.get("id"):
                vistos.add(x["id"])
for f in ("pl_pool.json",):                       # sus propias playlists
    p = os.path.join(HERE, f)
    if os.path.exists(p):
        vistos.update(json.load(open(p, encoding="utf-8")).keys())
print("ya vistos / ya enviados: %d" % len(vistos))

CANAL_GEN = {
 "André Navarro II": "citypop", "ants kask": "citypop", "JefferyBeats": "citypop",
 "TheRAREGROOVEMAN": "soul", "Soultwinz": "soul", "Casen Fike": "soul",
 "Krem Soulz": "soul", "aaappleknocker": "soul", "Athens of The North": "soul",
 "mikeejaylovessoul": "soul", "DJ Vinyl Goblin": "soul",
 "BigPeter1027 Real Music Channel": "80s",
 "Five Special Records": "rnb", "Winta Groove": "rnb", "skeenery": "rnb",
 "Neglected Trax": "rnb", "On the Rocks Records": "rnb", "si": "rnb",
 "JazzManDean": "fusion", "Cool Breeze": "fusion", "Elwood P. Dowd": "fusion",
 "The Voice of Anton": "fusion", "Vinyle Archéologie": "fusion",
 "foreal": "fusion", "Music for empty rooms": "fusion",
}
JP = re.compile(r"[぀-ヿ一-鿿]")

BASURA = re.compile(
    r"karaoke|tutorial|type beat|sample pack|reaction|how to|lyric video|megamix|"
    r"\bdj set\b|interview|entrevista|documental|full album|album completo|"
    r"compilation|visualizer|\bmix\b|unboxing|\bshorts?\b|teaser|trailer", re.I)
SEIS_OCHO = re.compile(r"\b6/8\b|\b12/8\b|\bwaltz\b|\bvals\b|\bvalse\b|\bvalzer\b", re.I)
ORTODOXO = re.compile(r"\b(bebop|be-bop|hard bop|dixieland|swing era|standards?|"
                      r"improvisation|\bjam\b|real book|blue note session)\b", re.I)
EFUSIVO = re.compile(r"\b(disco|dance|party|boogie down|shake|get down|stomp|hustle|"
                     r"rock ?n ?roll|twist|celebration|fiesta|workout|march|polka)\b", re.I)
INSTR = re.compile(r"\binstrumental\b|\(inst\.?\)|\[inst\.?\]", re.I)
# Nombres grandes: el upload puede tener 200 views, pero el tema lo conoce todo
# el mundo. Es el mismo error de medir obscuridad del upload y no de la obra.
CONOCIDOS = re.compile(
    r"\b(marvin gaye|roberta flack|smokey robinson|stevie wonder|aretha|"
    r"curtis mayfield|al green|barry white|isley|whitney|luther vandross|"
    r"anita baker|sade|teddy pendergrass|harold melvin|heatwave|con funk shun|"
    r"l\.?t\.?d\.?|bar.?kays|tavares|atlantic starr|klymaxx|millie jackson|"
    r"peaches & herb|the spinners|chi.?lites|delfonics|stylistics|o'?jays|"
    r"earth,? wind|kool & the gang|commodores|temptations|four tops|"
    r"gladys knight|patti labelle|phyllis hyman|angela bofill|willie hutch|"
    r"michael henderson|tyrone davis|dennis brown|herb alpert|george benson|"
    r"grover washington|bob james|roy ayers|lonnie liston|azymuth|"
    r"tatsuro yamashita|mariya takeuchi|anri|toshiki kadomatsu|casiopea|"
    r"ryo fukui|yuji ohno|hiroshi sato|takako mamiya|tomoko aran)\b", re.I)
# medleys: dos o tres temas pegados. Es "full album" disfrazado.
MEDLEY = re.compile(r"[^/]{8,}/[^/]{8,}/|[^/]{12,}/[^/]{12,}")
# el canal de city pop sube de todo: hay library italiana, jazz hungaro y latin
# soul de Nueva York mezclados. Para city pop se exige Japon de verdad.
JP_NOMBRE = re.compile(
    r"\b(yamashita|ohashi|kubota|yoshida|iwasaki|kadomatsu|anri|takeuchi|"
    r"matsubara|ohno|sugiyama|murata|hosono|sakamoto|yano|minako|mariya|taeko|"
    r"junko|akiko|toshiki|tatsuro|casiopea|naniwa|piper|momoko|rajie|miki|"
    r"inagaki|mizutani|shishido|gotoh|ueda|matsuura|morita|hart|kida)\b", re.I)
# fusion no es hiphop ni R&B de los 90
NO_FUSION = re.compile(r"\b(hip ?hop|rap\b|remix|dub\b|g-?funk|boom ?bap|"
                       r"freestyle|mixtape|beat ?tape)\b", re.I)
LENTO = re.compile(r"\b(love|rain|night|lonely|alone|dream|tears|cry|sad|blue|slow|"
                   r"ballad|theme|mood|soft|quiet|morning|heart|miss|goodbye|memory|"
                   r"remember|forever|tender|gentle|sweet|angel|star|moon|sky|sea|"
                   r"wind|autumn|silence|lament|nostalgia|prayer|interlude|reverie|"
                   r"romance|serenade|whisper|shadow|velvet|smooth|mellow|warm|"
                   r"peace|still|rhodes|strings|piano)\b", re.I)

def norm_art(t):
    t = re.sub(r"[⁦-⁩‎‏]", "", t)
    a = re.split(r"\s*[-–—:♪•|]\s*", t, 1)[0]
    a = unicodedata.normalize("NFKD", a.lower())
    return re.sub(r"[^a-z0-9぀-ヿ一-鿿]+", "", a)[:22]


def genero(vid, e):
    u = e.get("uploader") or ""
    g = e.get("gen_canal") or CANAL_GEN.get(u)
    t = e["title"]
    if JP.search(t) and g in (None, "fusion", "citypop"):
        return "citypop" if not re.search(r"fusion|jazz", t, re.I) else "fusion"
    if g == "modern":
        return "rnb"
    return g

cand = defaultdict(list)
desc = Counter()
for vid, e in pool.items():
    if vid in vistos:
        desc["ya enviado"] += 1; continue
    t = e["title"]
    d = e.get("dur") or 0
    v = e.get("views")
    if not d or d < 165 or d > 900:
        desc["duracion"] += 1; continue
    if BASURA.search(t):
        desc["basura"] += 1; continue
    if SEIS_OCHO.search(t):
        desc["6/8"] += 1; continue
    if v is not None and v > 300000:
        desc["mainstream >300k"] += 1; continue
    g = genero(vid, e)
    if not g:
        desc["sin genero"] += 1; continue
    if g == "fusion" and ORTODOXO.search(t):
        desc["jazz ortodoxo"] += 1; continue
    if g == "fusion" and NO_FUSION.search(t):
        desc["no es fusion"] += 1; continue
    if g == "citypop" and not (JP.search(t) or JP_NOMBRE.search(t)):
        desc["citypop sin Japon"] += 1; continue
    if v is not None and v < 150:
        desc["<150 views (rip casero)"] += 1; continue
    if CONOCIDOS.search(t):
        desc["nombre conocido"] += 1; continue
    if MEDLEY.search(t):
        desc["medley"] += 1; continue
    s = 0.0
    if INSTR.search(t): s += 1.4            # hueco instrumental asegurado
    if LENTO.search(t): s += 0.8
    if EFUSIVO.search(t): s -= 1.2
    if d >= 330: s += 0.8                   # 5:30+ : mas chance de pasaje libre
    elif d >= 240: s += 0.45
    if v is not None and 100000 < v <= 300000: s -= 0.5
    am = re.search(r"\b(19[4-9]\d|20[0-2]\d)\b", t)
    if am and 1968 <= int(am.group(1)) <= 1990: s += 0.5
    e.update({"id": vid, "gen": g, "pre": round(s, 2)})
    cand[g].append(e)

print("descartes: %s" % dict(desc.most_common()))
print()
CUPO = 34
sel = {}
for g, it in cand.items():
    it.sort(key=lambda x: -x["pre"])
    por_canal, por_art, out, n_inst = Counter(), Counter(), [], 0
    TOPE_INST = int(CUPO * 0.4)             # sin esto queda 34/34 instrumental
    for x in it:
        u = x.get("uploader") or "?"
        if por_canal[u] >= 12:              # que no lo cope un solo canal
            continue
        es_inst = bool(INSTR.search(x["title"]))
        if es_inst and n_inst >= TOPE_INST:
            continue
        art = norm_art(x["title"])
        if por_art[art] >= 2:               # nada de cuatro del mismo artista
            continue
        por_art[art] += 1
        por_canal[u] += 1
        n_inst += es_inst
        out.append(x)
        if len(out) >= CUPO:
            break
    # si el genero tiene un solo canal (el caso de 80s), el cupo de diversidad
    # lo deja corto: se completa igual, no tiene sentido entregar 12
    if len(out) < CUPO:
        ya = {x["id"] for x in out}
        for x in it:
            if x["id"] in ya:
                continue
            out.append(x)
            por_canal[x.get("uploader") or "?"] += 1
            if len(out) >= CUPO:
                break
    sel[g] = out
    print("%-8s candidatos %5d -> preseleccion %2d | canales: %s"
          % (g, len(it), len(out), [c for c, _ in por_canal.most_common(4)]))

todo = [x for v in sel.values() for x in v]
json.dump(sel, open(os.path.join(HERE, "demo_pre.json"), "w", encoding="utf-8"),
          ensure_ascii=False)
open(os.path.join(HERE, "demo_pre_ids.txt"), "w").write(" ".join(x["id"] for x in todo))
print("\na medir con el DSP: %d" % len(todo))
