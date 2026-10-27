# -*- coding: utf-8 -*-
"""Cava ENTEROS los canales que viven en las vetas que samplean Daringer,
Camoflauge Monk y Alchemist (library europea, bloque del este, jazz euro).
Antes los listé con tope de 300-600; acá van sin techo. yt-dlp flat = 0 quota."""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
YT = r"G:\Thomi - Mi Carpeta\crate_project\backend\.venv\Scripts\yt-dlp.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "ws_pool.json")
TOPE = 4000

CANALES = [
  ("UCY8_y20lxQhhBe8GZl5A9rw", "Music for empty rooms"),        # library europea etiquetada
  ("UC47qc6t2RelhfvI-OjgIY2A", "Rare Samples & Songs Oleg Tsoy"),  # bloque del este
  ("UCekevJPGTZ44nn_i4SWJDIw", "The Voice of Anton"),
  ("UC2xLCkq2twf355YoQggRTyQ", "foreal"),
  ("UCAE-UJvklqnSs96vmdu6vQw", "DJ Vinyl Goblin"),
  ("@VinyleArcheologie",       "Vinyle Archéologie"),
  ("UCr79VNMYJiZCIUrBt9le6kQ", "JazzManDean"),
  ("UCEm5THU0Fg1hOYxgONkTmug", "Elwood P. Dowd"),
  ("UCP-R7czth3VnJZL_lwA829Q", "Cool Breeze"),
]
SEP = chr(92) + "t"   # yt-dlp imprime el \t literal, no un tab

def cavar(arg):
    cid, nombre = arg
    url = f"https://www.youtube.com/{cid}/videos" if cid.startswith("@") \
          else f"https://www.youtube.com/channel/{cid}/videos"
    cmd = [YT, "--flat-playlist", "--no-warnings", "-q", "--ignore-errors",
           "-I", f"1:{TOPE}", "--print",
           f"%(id)s{SEP}%(title)s{SEP}%(duration)s{SEP}%(view_count)s", url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=900)
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT {nombre}", flush=True); return nombre, {}
    got = {}
    for ln in r.stdout.splitlines():
        p = ln.split(SEP)
        if len(p) < 4 or len(p[0]) != 11: continue
        got[p[0]] = {"title": p[1], "uploader": nombre,
                     "dur": int(p[2]) if p[2].isdigit() else None,
                     "views": int(p[3]) if p[3].isdigit() else None}
    print(f"  {nombre}: {len(got)}", flush=True)
    return nombre, got

if not os.path.exists(YT):
    sys.exit(f"no encuentro yt-dlp en {YT}")
pool = {}
with ThreadPoolExecutor(max_workers=4) as ex:
    for nombre, got in ex.map(cavar, CANALES):
        pool.update(got)
json.dump(pool, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
print(f"\nTOTAL cavado: {len(pool)} -> ws_pool.json")
