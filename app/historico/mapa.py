"""Reconstruye el mapeo número-de-lista → video id, igual que se imprimió vetas_lista.txt."""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
pool = json.load(open(os.path.join(HERE, "vetas_pool.json"), encoding="utf-8"))
rows_ids = json.load(open(os.path.join(HERE, "vetas_rows.json")))
rows_set = set(rows_ids)
GRUPO = {
 'soul70': ["TheRAREGROOVEMAN","Soultwinz","Casen Fike","aaappleknocker","Five Special Records","DJ Vinyl Goblin","Krem Soulz","secondscene"],
 'modern': ["si","Winta Groove","skeenery","Neglected Trax","On the Rocks Records","BigPeter1027 Real Music Channel","mikeejaylovessoul","Athens of The North"],
 'japon': ["André Navarro II","ants kask","JefferyBeats"],
 'fusion': ["JazzManDean","Elwood P. Dowd","Cool Breeze","The Voice of Anton","Vinyle Archéologie","Dusty Breaks"],
 'raro': ["Music for empty rooms","Rare Samples & Songs Oleg Tsoy","foreal"],
}
inv = {u: g for g, us in GRUPO.items() for u in us}
RUIDO = re.compile(r'karaoke|tutorial|full album|album completo|lyrics video|reaction|unboxing|how to', re.I)
rows = []
for i, e in pool.items():
    if i not in rows_set: continue
    d = e['dur'] or 0
    if d and (d < 75 or d > 1200): continue
    if RUIDO.search(e['title']): continue
    rows.append((inv.get(e['uploader'], 'otros'), e['uploader'], i, e['title'], d, e['views']))
mapa, n = {}, 0
for g in ['soul70','modern','japon','fusion','raro','otros']:
    sub = [r for r in rows if r[0] == g]
    for u in sorted({r[1] for r in sub}):
        for r in [x for x in sub if x[1] == u]:
            n += 1
            mapa[n] = {"id": r[2], "title": r[3], "uploader": r[1], "dur": r[4], "views": r[5], "grupo": g}
json.dump(mapa, open(os.path.join(HERE, "mapa.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("mapeados:", len(mapa))
for k in (1, 292, 483, 682, 908, 2549, 4799, 4987, 5284, 5481, 6572):
    if k in mapa: print(f"  {k}: {mapa[k]['title'][:62]} | {mapa[k]['uploader']}")
