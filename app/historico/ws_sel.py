# -*- coding: utf-8 -*-
"""Selección balanceada de la 2da tanda. Sin cupos, 'Music for empty rooms' se
come la lista entera: etiqueta país+género+año y por eso siempre puntúa alto.
Cupo por canal, por semilla y por país, para que la entrega tenga variedad real."""
import json, os, re
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
fin = json.load(open(os.path.join(HERE, "ws_finalistas.json"), encoding="utf-8"))

PAIS = re.compile(r"\[([^\]]+)\]")
def pais_de(t):
    m = PAIS.search(t)
    return m.group(1).split(",")[0].strip()[:18] if m else "?"

# la punta "hermano" es la que viene de discos ya validados por el palo de Thomas
# (Roc Marci, Benny, Conway, Craven, Estee Nack): pesa mas que la veta general.
OBJ_HERMANO, OBJ_VETA = 100, 90
CUPO_CANAL, CUPO_SEMILLA, CUPO_PAIS = 26, 5, 22
# sin cupo por productor, Craven y Knxwledge (que puntúan primero) se comen la
# lista y Benny, Conway o Estee Nack quedan con uno. Thomas los nombró a todos.
CUPO_PROD = 13

sel, por_canal, por_sem, por_pais = [], Counter(), Counter(), Counter()
por_prod = Counter()

def tomar(x, cupos_pais=True):
    u = x.get("uploader") or "?"
    if por_canal[u] >= CUPO_CANAL: return False
    if x["punta"] == "hermano":
        s, q = x.get("semilla", "?"), x.get("quien", "?")
        if por_sem[s] >= CUPO_SEMILLA: return False
        if por_prod[q] >= CUPO_PROD: return False
        por_sem[s] += 1
        por_prod[q] += 1
    else:
        p = pais_de(x["title"])
        if cupos_pais and p != "?" and por_pais[p] >= CUPO_PAIS: return False
        por_pais[p] += 1
    por_canal[u] += 1
    sel.append(x)
    return True

for x in [y for y in fin if y["punta"] == "hermano"]:
    if len([s for s in sel if s["punta"] == "hermano"]) >= OBJ_HERMANO: break
    tomar(x)
for x in [y for y in fin if y["punta"] == "veta"]:
    if len([s for s in sel if s["punta"] == "veta"]) >= OBJ_VETA: break
    tomar(x)

sel.sort(key=lambda y: -y["score"])
json.dump(sel, open(os.path.join(HERE, "ws_sel.json"), "w", encoding="utf-8"), ensure_ascii=False)
open(os.path.join(HERE, "ws_sel_ids.txt"), "w").write(" ".join(x["id"] for x in sel))
print("seleccionados: %d  (hermanos %d / veta %d)" % (
    len(sel), sum(1 for x in sel if x["punta"] == "hermano"),
    sum(1 for x in sel if x["punta"] == "veta")))
print("\ncanales:", por_canal.most_common(10))
print("\npaíses:", por_pais.most_common(12))
print("\nsemillas:", por_sem.most_common(10))
