# -*- coding: utf-8 -*-
"""Cava ENTERO Five Special Records: el mejor canal de Thomas (56% de hit rate,
26 guardados de 46 marcados) del que solo tenia listados 200 de 4.351 temas."""
import json, os, subprocess
YT = r"G:\Thomi - Mi Carpeta\crate_project\backend\.venv\Scripts\yt-dlp.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
SEP = chr(92) + "t"
CID = "UC8miJX57wgdexh0Wb7z8wBA"

cmd = [YT, "--flat-playlist", "--no-warnings", "-q", "--ignore-errors",
       "--print", "%%(id)s%s%%(title)s%s%%(duration)s%s%%(view_count)s" % (SEP, SEP, SEP),
       "https://www.youtube.com/channel/%s/videos" % CID]
r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=1800)
pool = {}
for ln in r.stdout.splitlines():
    c = ln.split(SEP)
    if len(c) < 4 or len(c[0]) != 11:
        continue
    pool[c[0]] = {"title": c[1], "uploader": "Five Special Records",
                  "dur": int(c[2]) if c[2].isdigit() else None,
                  "views": int(c[3]) if c[3].isdigit() else None}
json.dump(pool, open(os.path.join(HERE, "fsr_pool.json"), "w", encoding="utf-8"),
          ensure_ascii=False)
print("Five Special Records cavado entero: %d temas" % len(pool))

# lo que ya vio o ya le mande
vistos = set()
for f in ("sel_ids.txt", "latam_ids.txt", "sierra_ids.txt", "preselect_ids.txt", "ws_sel_ids.txt"):
    p = os.path.join(HERE, f)
    if os.path.exists(p):
        vistos.update(open(p).read().split())
for f in ("vetas_pool.json", "pl_pool.json"):
    p = os.path.join(HERE, f)
    if os.path.exists(p):
        vistos.update(json.load(open(p, encoding="utf-8")).keys())
nuevo = {k: v for k, v in pool.items() if k not in vistos}
print("nunca vistos: %d" % len(nuevo))
d = [v["dur"] for v in nuevo.values() if v.get("dur")]
vw = [v["views"] for v in nuevo.values() if v.get("views") is not None]
if d:
    d.sort(); vw.sort()
    print("duracion mediana %d:%02d | views mediana %d" % (
        d[len(d)//2]//60, d[len(d)//2]%60, vw[len(vw)//2] if vw else 0))
    print("con views >300k (fuera por mainstream): %d" % sum(1 for v in vw if v > 300000))
    print("de 2:45 a 15:00: %d" % sum(1 for x in d if 165 <= x <= 900))
json.dump(nuevo, open(os.path.join(HERE, "fsr_nuevo.json"), "w", encoding="utf-8"),
          ensure_ascii=False)
