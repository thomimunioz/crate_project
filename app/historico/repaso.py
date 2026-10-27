# -*- coding: utf-8 -*-
"""Re-pasa los temas de las 5 listas v2 que Thomas todavia no marco, para que no
pierda tiempo escuchando lo que ya sabemos que no va.

SOLO usa señales MEDIDAS contra sus 113 marcas reales. Las señales inventadas
(año, views, duracion, BPM, tonalidad, confianza del DSP) dieron AUC 0.43-0.57
sobre su feedback, o sea ruido, asi que no se usan para rankear.

Lo que si esta medido:
  * tier que le puse a mano: fuego 63% vs bien 37%
  * canal: Five Special 74%, BigPeter1027 54%, JefferyBeats 30%
  * lista: R&B 74%, city pop 57%, 80s 54%, fusion 30%
Mas filtros duros que salen de sus motivos textuales, no de suposiciones.
"""
import json, os, re, glob
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
sel = json.load(open(os.path.join(HERE, "seleccion.json"), encoding="utf-8"))
meta = json.load(open(os.path.join(HERE, "meta_cache.json"), encoding="utf-8"))
bpm = json.load(open(os.path.join(HERE, "bpm_cache.json"), encoding="utf-8"))
marc = json.load(open(os.path.join(HERE, "marcados.json"), encoding="utf-8"))

# --- hit rate medido, suavizado con un prior para que 3/3 no valga 100% ---
ALFA, BASE = 8.0, 0.59
def tasa(g, n):
    return (g + ALFA * BASE) / (n + ALFA)

cnt = defaultdict(lambda: [0, 0])          # clave -> [guardados, marcados]
rech_art = Counter()                        # artista -> rechazos duros
for f in glob.glob(r"C:\Users\thomi\Downloads\crate-feedback-*.json"):
    for t in json.load(open(f, encoding="utf-8"))["temas"]:
        e = next((x for x in sel if x["id"] == t["id"]), None)
        if not e:
            continue
        # abierto y NO guardado = rechazo implicito (Thomas, 24-oct):
        # "los que estan vistos y no comentados no los guarde"
        ok = 1 if t.get("agregado") else 0
        if not (t.get("agregado") or t.get("motivo") or t.get("abierto")):
            continue
        for k in (("canal", e.get("uploader")), ("tier", e.get("tier")),
                  ("lista", e.get("playlist"))):
            cnt[k][0] += ok; cnt[k][1] += 1
        if not ok and t.get("motivo") in ("mainstream", "efusivo", "rip"):
            a = re.split(r"\s+[-–—]\s+", t["titulo"])[0][:28].strip().lower()
            rech_art[a] += 1

print("=== hit rate medido (n = marcados) ===")
for tipo in ("lista", "tier", "canal"):
    for (t, v), (g, n) in sorted(cnt.items(), key=lambda kv: -kv[1][1]):
        if t == tipo and n >= 3:
            print("  %-7s %-34s %2d/%2d  %3d%%  -> suavizado %.2f"
                  % (t, str(v)[:34], g, n, 100 * g // n, tasa(g, n)))

def artista(t):
    return re.split(r"\s+[-–—]\s+", t)[0][:28].strip().lower()

# --- filtros duros: salen de motivos textuales, no de suposiciones ---
def duro(e):
    m = meta.get(e["id"], {})
    v = m.get("views") if m.get("views") is not None else e.get("views")
    d = e.get("dur") or 0
    b = bpm.get(e["id"], {})
    bb = b.get("bpm")
    if bb and bb > 115 and 55 <= bb / 2 <= 115:
        bb = bb / 2
    razones = []
    if v and v > 300000:
        razones.append("%.1fM views: mainstream" % (v / 1e6) if v >= 1e6
                       else "%dk views: mainstream" % (v // 1000))
    if d and d < 150:
        razones.append("%d:%02d, muy corto" % (d // 60, d % 60))
    if bb and bb > 115:
        razones.append("%d BPM real" % round(bb))
    if rech_art.get(artista(e["title"]), 0) >= 1:
        razones.append("ya rechazaste a este artista")
    return razones

pend = [e for e in sel if e["id"] not in marc]
print("\n=== %d temas sin marcar, de %d entregados ===" % (len(pend), len(sel)))

for e in pend:
    p = (tasa(*cnt[("canal", e.get("uploader"))]) * 0.4
         + tasa(*cnt[("tier", e.get("tier"))]) * 0.35
         + tasa(*cnt[("lista", e.get("playlist"))]) * 0.25)
    e["p"] = round(p, 3)
    e["duro"] = duro(e)

fuera = [e for e in pend if e["duro"]]
queda = sorted([e for e in pend if not e["duro"]], key=lambda x: -x["p"])
print("salen por filtro duro: %d" % len(fuera))
print("quedan para escuchar:  %d" % len(queda))
print("\n--- los que SALEN ---")
for e in sorted(fuera, key=lambda x: x["playlist"]):
    print("  [%-7s] %-52s" % (e["playlist"], e["title"][:52]))
    print("            %s" % "; ".join(e["duro"]))
json.dump({"fuera": fuera, "queda": queda},
          open(os.path.join(HERE, "repaso.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("\n--- top 12 de los que quedan (por probabilidad medida) ---")
for e in queda[:12]:
    print("  %.2f [%-7s] %s %s" % (e["p"], e["playlist"],
          {"fuego": "F", "bien": "B", "quizas": "Q"}.get(e["tier"], "?"), e["title"][:54]))
