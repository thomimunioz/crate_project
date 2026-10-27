# -*- coding: utf-8 -*-
"""Consolida las dos puntas de la 2da tanda:
  A) hermanos de discos que los productores de Thomas ya samplearon (sin el corte usado)
  B) los 21k nuevos de los canales de library europea / bloque del este
Aplica el oido medido de Thomas y deduplica. Deja finalistas para medir con el DSP."""
import json, os, re, unicodedata
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
APOS = "’"

def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    for ch in ("'", APOS, "`"):          # el apostrofe NO separa palabras
        s = s.replace(ch, "")
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower()).strip()

def clave(t):
    """Titulo sin anio, corchetes ni n de track: para deduplicar el mismo tema."""
    t = re.sub(r"\(.*?\)|\[.*?\]|\b(19|20)\d{2}\b|℗|\bmono\b|\bstereo\b|"
               r"\bremaster\w*\b|\bvinyl\b|\bHQ\b|\bHD\b", " ", t, flags=re.I)
    t = re.sub(r"^\s*\d{1,2}\s*[-.•]?\s*", "", t)
    return re.sub(r"\s+", " ", norm(t))

# el tema que cada productor YA uso: ese esta quemado por definicion
QUEMADO = {
 "Faith Hope & Charity": ["keep me baby"], "Zingara": ["loves calling"],
 "Sound Experience": ["you dont know what youre doing"], "The Raes": ["to love somebody"],
 "The Futures": ["deep inside of me"], "Miquel Brown": ["do it"],
 "Diann Franklin": ["hes there"], "Gloria Scott": ["i just couldnt take a goodbye"],
 "Prince Harold": ["forget about me"], "Odyssey 5": ["peace of mind"],
 "Jorge Dalto": ["for openers"], "Wendy Saddington": ["i think of you"],
 "Monk Higgins": ["i believe to my soul", "railroad"], "Derrick Erni": ["never"],
 "Eugene Record": ["when we pull the shades"], "Frank Cunimondo Trio": ["love so fine"],
 "Sweet Thursday": ["gilbert street"], "Lesiman": ["sbarramento"],
 "John Fiddy": ["baddy"], "Michel Colombier": ["morning is come again"],
 "Thijs Van Leer": ["street rondo"], "Howard Lemon Singers": ["i know god is real"],
 "Gianni Marchetti": ["february"], "Francois de Roubaix": ["les dunes dostende"],
 "Zdzislawa Sosnicka": ["dobranocka"], "Stan Tracey": ["starless and bible black"],
 "Ian Carr Nucleus": ["remadione"], "Dave Greenslade": ["dry land"],
 "Sergei Manukjan": ["looking for you"], "Svika Pick": ["false stars"],
 "Cem Karaca": ["sevdan beni"], "Riff Raff": ["havakak"],
 # --- ronda 2: semillas del palo (Roc Marci, Benny, Conway, Estee Nack, Al.Divino) ---
 "Ronnie McNeir": ["spirit of love"], "The Holy Light Jr": ["love hides all faults"],
 "Smoked Sugar": ["keeping up my front"], "Astra Nova Orchestra": ["soul sleeper"],
 "Mighty Doug Haynes": ["honey"], "Turner Bros": ["sweetest thing in the world"],
 "Anna German": ["zhdu vesnu", "jestem spragniona"], "I Nomadi": ["eterno"],
 "Bernard Callais": ["final"], "Greg Perry": ["come fly with me"],
 "Timo Laine": ["do me slow"], "Yasuko Kawashima": ["omoide no screen"],
 "A.A.B.B.": ["pick up the pieces"], "Full Speed": ["it must be love"],
 "Billy Cobham": ["siesta", "wake up"], "Bread": ["everything i own"],
}
# Fuera por volumen de samples reales, verificado en WhoSampled. El peso real
# no es el número: es QUIÉN. Monk Higgins lo usaron Madlib (Madvillainy) y
# Gang Starr; Umiliani y Ferrio los usó Pete Rock. Eso es el mismo palo
# cavando el mismo pozo, así que esos ya están exprimidos para este oído.
QUEMADOS_ART = re.compile(
    r"umiliani|nilovic|bruno nicolai|alessandroni|ortolani|gianni ferrio|"
    r"stelvio cipriani|keith mansfield|alan hawkshaw|brian bennett|johnny pearson|"
    r"keith jarrett|ryo fukui|yuji ohno|david axelrod|\bsade\b|crystal gayle|"
    r"honey cone|five stairsteps|rance allen|monk higgins|gloria ann taylor|"
    r"lou courtney|gato barbieri|\bC\.?A\.? quintet\b", re.I)

vistos = set()
for f in ("sel_ids.txt", "latam_ids.txt", "sierra_ids.txt", "preselect_ids.txt"):
    p = os.path.join(HERE, f)
    if os.path.exists(p):
        vistos.update(open(p).read().split())
for f in ("seleccion.json", "fuego.json"):
    p = os.path.join(HERE, f)
    if os.path.exists(p):
        d = json.load(open(p, encoding="utf-8"))
        for x in (d if isinstance(d, list) else d.values()):
            if isinstance(x, dict) and x.get("id"):
                vistos.add(x["id"])
for f in ("vetas_pool.json", "latam_pool.json"):     # ya listado antes de hoy
    p = os.path.join(HERE, f)
    if os.path.exists(p):
        vistos.update(json.load(open(p, encoding="utf-8")).keys())
print("ya vistos / ya listados antes: %d" % len(vistos))

BASURA = re.compile(
    r"karaoke|tutorial|type beat|sample pack|reaction|how to|lyric|\bmix\b|megamix|"
    r"dj set|interview|entrevista|documental|\blive\b|en vivo|cover by|\bremix\b|"
    r"\bedit\b|full album|album completo|compilation|visualizer", re.I)
RAPIDO = re.compile(
    r"\b(disco|dance|party|boogie|shake|funky|get down|stomp|hustle|rock ?n ?roll|"
    r"twist|jump|celebration|fiesta|hot|fire|crazy|wild|freak|bump|shout|workout|"
    r"march|marcia|galop|polka|csardas|samba|carnaval)\b", re.I)
LENTO = re.compile(
    r"\b(love|amour|amore|rain|pioggia|night|notte|nuit|lonely|alone|solo|dream|sogno|"
    r"reve|tears|cry|sad|triste|blue|slow|ballad|ballata|theme|tema|mood|soft|quiet|"
    r"morning|heart|cuore|miss|goodbye|addio|memory|ricordo|souvenir|remember|forever|"
    r"tender|gentle|sweet|dolce|angel|star|stella|moon|luna|sky|cielo|sea|mare|wind|"
    r"vento|autumn|autunno|silence|silenzio|waltz|valzer|lament|nostalgia|elegy|prayer|"
    r"preghiera|interlude|reverie|romance|romantica|serenade|serenata|whisper|shadow|"
    r"ombra|mist|velvet|smooth|mellow|warm|peace|pace|still|adagio|andante|lento|"
    r"nocturne|notturno|ninna|piano|rhodes|fender|strings|archi|flute|flauto|harp|"
    r"arpa|attesa|solitudine)\b", re.I)
# el canal "Music for empty rooms" declara [Pais] Genero (Anio) en el titulo
MFER = re.compile(r"\[([^\]]+)\]\s*([^(]+)\((\d{4})\)")
GEN_OK = re.compile(r"library|score|jazz|soul|easy listening|downtempo|ambient|balear|"
                    r"fusion|bossa|mpb|lo-?fi|psych", re.I)
GEN_NO = re.compile(r"\bdisco\b|\bfunk\b|boogie|rock|punk|metal|new wave|house|techno|"
                    r"reggae|ska|garage|surf|country", re.I)

cands, desc = [], Counter()

# --- punta A: hermanos de los discos ya sampleados (las dos rondas de semillas) ---
semillas = {}
for f in ("ws_semillas.json", "ws_semillas2.json"):
    p = os.path.join(HERE, f)
    if os.path.exists(p):
        for k, v in json.load(open(p, encoding="utf-8")).items():
            semillas.setdefault(k, v)
for vid, e in semillas.items():
    t, sem = e["title"], e["semilla"]
    nt, ns = norm(t), norm(sem)
    if vid in vistos:
        desc["A ya visto"] += 1; continue
    d = e.get("dur") or 0
    if not d or d < 95 or d > 900:
        desc["A duracion"] += 1; continue
    if BASURA.search(t):
        desc["A basura"] += 1; continue
    if QUEMADOS_ART.search(t):
        desc["A artista quemado"] += 1; continue
    if not all(w in nt for w in ns.split() if len(w) > 3):
        desc["A no es el artista"] += 1; continue
    if any(q in nt for q in QUEMADO.get(sem, [])):
        desc["A corte ya sampleado"] += 1; continue
    e.update({"id": vid, "punta": "hermano", "via": "%s sampleo a %s" % (e["quien"], sem)})
    cands.append(e)

# --- punta B: los 21k nuevos de canales de library / este ---
VETA = re.compile(
    r"\blibrary\b|\bKPM\b|de ?wolfe|bruton|sonoton|selected sound|chappell|\bscore\b|"
    r"soundtrack|colonna sonora|\[italy\]|\[france\]|\[poland\]|\[germany\]|\[czech|"
    r"\[hungar|\[yugoslav|\[soviet|\[ussr|\[russia|\[bulgar|\[roman|\[eston|\[latv|"
    r"polskie|polski|мелодия|melodiya|supraphon|"
    r"pepita|balkanton|jugoton|easy listening|jazz|soul|bossa|fusion", re.I)
for vid, e in json.load(open(os.path.join(HERE, "ws_pool.json"), encoding="utf-8")).items():
    t = e["title"]
    if vid in vistos:
        desc["B ya visto"] += 1; continue
    d = e.get("dur") or 0
    if not d or d < 95 or d > 900:
        desc["B duracion"] += 1; continue
    if BASURA.search(t):
        desc["B basura"] += 1; continue
    if QUEMADOS_ART.search(t):
        desc["B artista quemado"] += 1; continue
    if not VETA.search(t):
        desc["B fuera de veta"] += 1; continue
    e.update({"id": vid, "punta": "veta", "via": "canal %s" % e["uploader"],
              "escuela": "library_este"})
    cands.append(e)

# --- scoring con el oido medido ---
for x in cands:
    t = x["title"]
    s = 0.0
    if LENTO.search(t): s += 1.0
    if RAPIDO.search(t): s -= 1.3
    v = x.get("views")
    if v is not None:
        if v > 600000: s -= 1.8
        elif v > 150000: s -= 0.7
        elif 800 <= v <= 60000: s += 0.6
        elif v < 150: s -= 0.3
    d = x.get("dur") or 0
    if 170 <= d <= 450: s += 0.7
    elif 450 < d <= 620: s += 0.25
    elif d < 140: s -= 0.5
    m = MFER.search(t)
    if m:
        s += 0.4
        if GEN_OK.search(m.group(2)): s += 0.9
        if GEN_NO.search(m.group(2)): s -= 1.0
        if 1968 <= int(m.group(3)) <= 1988: s += 0.5
    else:
        am = re.search(r"\b(19[4-9]\d|20[0-2]\d)\b", t)
        if am and 1968 <= int(am.group(1)) <= 1988: s += 0.5
    if x["punta"] == "hermano":
        s += 0.8          # disco ya validado por un productor que le gusta
    x["score"] = round(s, 2)

# --- dedup por tema ---
mejor = {}
for x in sorted(cands, key=lambda y: -y["score"]):
    k = clave(x["title"])[:70]
    if len(k) < 6:
        continue
    if k not in mejor:
        mejor[k] = x
fin = sorted(mejor.values(), key=lambda y: -y["score"])
print("descartes: %s" % dict(desc.most_common()))
print("\ncandidatos: %d -> tras dedup: %d" % (len(cands), len(fin)))
print("por punta: %s" % dict(Counter(x["punta"] for x in fin)))
json.dump(fin, open(os.path.join(HERE, "ws_finalistas.json"), "w", encoding="utf-8"),
          ensure_ascii=False)
print("\n=== top 25 ===")
for x in fin[:25]:
    v = x.get("views")
    vs = "?" if v is None else ("%dk" % (v // 1000) if v >= 1000 else str(v))
    print("  %+.1f %-60s|%6s| %s" % (x["score"], x["title"][:60], vs, x["via"][:34]))
