# -*- coding: utf-8 -*-
"""Tanda de INSTRUMENTALES DE EPOCA.

Thomas, 25-oct-2026: "conseguis INSTRUMENTALES de esos temas de epoca, eso es
ORO PURO, ninguna vocal, se pueden hacer mil beats con eso. Nunca se me ocurrio...
Siempre y cuando cumplan el criterio OBVIO".

Por que importa: su problema de siempre es el espacio — que no canten todo el
tema. Un instrumental no tiene "un hueco": es todo hueco. Y a diferencia de
cualquier otra señal, esta se lee del titulo, no hace falta medir el audio (que
es justamente lo que no logre implementar).

El "criterio OBVIO" es todo lo demas que ya sabemos: tempo bajo, tonalidad
menor preferida, nada mainstream, nada efusivo, nada corto, nada repetido.
"""
import json, os, re, unicodedata
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
pool = {}
for f in ("demo_cavado.json", "fsr_nuevo.json", "ws_pool.json",
          "vetas_pool.json", "latam_pool.json"):
    p = os.path.join(HERE, f)
    if os.path.exists(p):
        for k, v in json.load(open(p, encoding="utf-8")).items():
            pool.setdefault(k, v)

# --- nucleo duro: el titulo DECLARA que no hay voz ---
# "version" sola queda afuera a proposito: en soul suele ser "7 Inch Version",
# que si tiene voz. En reggae si significa instrumental, pero no vale el ruido.
SIN_VOZ = re.compile(
    r"\binstrumental\b|\(inst\.?\)|\[inst\.?\]|\binst\.\s|"
    r"\bdub\b|off ?vocal|オフボーカル|"
    r"backing track|minus one|\bplayback\b|\bTV (mix|track|size)\b|"
    r"\brhythm track\b|\bunderscore\b", re.I)
# karaoke moderno: eso es MIDI, no el instrumental del disco
FALSO = re.compile(r"karaoke version|midi|\bcover\b|remake|re-?recorded|"
                   r"type beat|sample pack|tutorial", re.I)
# EL BUG DEL 27-oct: en soul y boogie "dub" es la version instrumental del 12",
# pero en REGGAE dub es un genero entero. Se colaron 12 reggae y Thomas escribio
# "ES REGGAE" trece veces. Hay que separar los dos sentidos de la palabra.
REGGAE = re.compile(
    r"\breggae\b|\bdancehall\b|\broots\b|\briddim\b|\brocksteady\b|\bska\b|"
    r"\bdub ?plate\b|\bdub version\b|\bdub on\b|\blovers rock\b|\bskank\b|"
    r"johnny clarke|janet kay|sugar minott|dub syndicate|chosen few|king tubby|"
    r"scientist|studio one|lee ?perry|augustus pablo|\bjah\b|\bi-?roy\b|"
    r"gregory isaacs|horace andy|burning spear|black uhuru|\btrojan\b|"
    r"bob marley|wailers|weapon of peace|toots|maytals|\bupsetters\b|"
    r"\bmighty diamonds\b|\bculture\b.*\bdub\b|\baswad\b|\bsteel pulse\b", re.I)
# "dub" usado como ETIQUETA DE GENERO (no como "version instrumental del 12\""):
#   "... | DUB"   "[France] Soul, Afro Jazz, Dub (1996)"   "... - BUFFALO DUB"
# Si viene detras de un pipe, dentro de una lista de generos, o suelto en
# mayusculas al final, es el genero jamaiquino y no la mezcla sin voz.
DUB_GENERO = re.compile(
    r"\|\s*dub\b|,\s*dub\b|\bdub\s*[\|\(\[]|\bdub\s*$|\bDUB\b(?=\s*$)", re.I)
# canales que mezclan reggae con soul: ahi un "dub" es sospechoso por defecto
CANAL_REGGAE = {"aaappleknocker"}

vistos = set()
for f in ("sel_ids.txt", "demo_pre_ids.txt", "preselect_ids.txt", "ws_sel_ids.txt",
          "latam_ids.txt", "sierra_ids.txt"):
    p = os.path.join(HERE, f)
    if os.path.exists(p):
        vistos.update(open(p).read().split())
for f in ("pl_pool.json",):
    p = os.path.join(HERE, f)
    if os.path.exists(p):
        vistos.update(json.load(open(p, encoding="utf-8")).keys())

CONOCIDOS = re.compile(
    r"\b(marvin gaye|roberta flack|smokey robinson|stevie wonder|aretha|"
    r"curtis mayfield|al green|barry white|isley|whitney|luther vandross|"
    r"anita baker|\bsade\b|teddy pendergrass|harold melvin|heatwave|"
    r"con funk shun|l\.?t\.?d\.?|bar.?kays|tavares|atlantic starr|klymaxx|"
    r"millie jackson|the spinners|chi.?lites|delfonics|stylistics|o'?jays|"
    r"earth,? ?wind|kool & the gang|commodores|temptations|four tops|"
    r"gladys knight|patti labelle|phyllis hyman|change\b|shalamar|"
    r"george benson|grover washington|bob james|roy ayers|donna summer)\b", re.I)
EFUSIVO = re.compile(r"\b(disco|dance|party|shake|get down|stomp|hustle|"
                     r"rock ?n ?roll|twist|celebration|workout|march)\b", re.I)

def norm_art(t):
    a = re.split(r"\s*[-–—:|♪•]\s*", t, 1)[0]
    a = unicodedata.normalize("NFKD", a.lower())
    return re.sub(r"[^a-z0-9]+", "", a)[:20]

cand, desc = [], Counter()
for vid, e in pool.items():
    t = e["title"]
    if not SIN_VOZ.search(t):
        continue
    if vid in vistos:
        desc["ya visto"] += 1; continue
    if FALSO.search(t):
        desc["karaoke moderno / cover"] += 1; continue
    if REGGAE.search(t) or DUB_GENERO.search(t):
        desc["reggae (dub es otro genero ahi)"] += 1; continue
    if (e.get("uploader") in CANAL_REGGAE) and re.search(r"\bdub\b", t, re.I):
        desc["dub de canal reggae"] += 1; continue
    d = e.get("dur") or 0
    if d < 165 or d > 900:
        desc["duracion"] += 1; continue
    v = e.get("views")
    if v is not None and v > 300000:
        desc["mainstream"] += 1; continue
    if v is not None and v < 150:
        desc["<150 views"] += 1; continue
    if CONOCIDOS.search(t):
        desc["nombre conocido"] += 1; continue
    s = 0.0
    if re.search(r"\bdub\b", t, re.I): s += 0.6      # el dub respira distinto
    if d >= 330: s += 1.0
    elif d >= 240: s += 0.5
    if EFUSIVO.search(t): s -= 1.3
    am = re.search(r"\b(19[5-9]\d|200\d)\b", t)
    if am and 1968 <= int(am.group(1)) <= 1990: s += 0.4
    e.update({"id": vid, "pre": round(s, 2)})
    cand.append(e)

print("descartes: %s" % dict(desc.most_common()))
print("candidatos instrumentales nuevos: %d" % len(cand))

cand.sort(key=lambda x: -x["pre"])
por_canal, por_art, sel = Counter(), Counter(), []
for x in cand:
    u = x.get("uploader") or "?"
    a = norm_art(x["title"])
    if por_canal[u] >= 10 or por_art[a] >= 2:
        continue
    por_canal[u] += 1; por_art[a] += 1
    sel.append(x)
    if len(sel) >= 60:
        break
json.dump(sel, open(os.path.join(HERE, "inst_pre.json"), "w", encoding="utf-8"),
          ensure_ascii=False)
open(os.path.join(HERE, "inst_ids.txt"), "w").write(" ".join(x["id"] for x in sel))
print("preseleccion: %d" % len(sel))
print("canales: %s" % por_canal.most_common(8))
