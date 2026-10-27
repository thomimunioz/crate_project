# -*- coding: utf-8 -*-
"""Cava enteros los canales de city pop, soul y 80s/modern que seguian topeados.
Para la demo hacen falta 10 buenos de CADA genero, y hoy el pool esta inflado de
library europea (JazzManDean, Oleg Tsoy) y flaco en city pop y soul."""
import json, os, subprocess
from concurrent.futures import ThreadPoolExecutor
YT = r"G:\Thomi - Mi Carpeta\crate_project\backend\.venv\Scripts\yt-dlp.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
SEP = chr(92) + "t"
TOPE = 3000

CANALES = [
  # city pop (hoy: 517 + poco mas)
  ("UCv5OAW45h67CJEY6kJLyisg", "André Navarro II", "citypop"),
  ("UC4rdJibQ4NfeJxGbg4rvNxw", "ants kask", "citypop"),
  ("UCnVk2SYJ3ZIhp0FCB9a1EGg", "JefferyBeats", "citypop"),
  # soul 70s
  ("UCE-O0L9EzmoEcM69E3QjGTg", "TheRAREGROOVEMAN", "soul"),
  ("UCiMAhn-OD_XA8T_reQMcwMA", "Soultwinz", "soul"),
  ("UCXV_UkAxldqySLJ-FNqFnCA", "Casen Fike", "soul"),
  ("UCEiSkaHC2pejVpfC90jeANg", "Krem Soulz", "soul"),
  ("UCkjBeNtQtmhGOkEegI2W5_g", "aaappleknocker", "soul"),
  ("UCEfDmBvn1UduuZ84xHB09lQ", "Athens of The North", "soul"),
  # 80s / modern soul de sello chico
  ("UCL8EjPRV5WxrpzU4vn7j8eQ", "BigPeter1027 Real Music Channel", "80s"),
  ("UC546_voUGtgQr5LmtWV-4pQ", "Winta Groove", "modern"),
  ("UC1r_Q42GyLb2I1mL0L1Mxqw", "skeenery", "modern"),
  ("UCYPltVawiS_dVsyv13hERgw", "Neglected Trax", "modern"),
  ("UCwF7X0M0RH3ryBGgy8QiDCA", "On the Rocks Records", "modern"),
  ("UCTFuQaZ4XJ0jQO1MJ4dYFXw", "si", "modern"),
  ("UC8U4Px_RbJat4_4LKJ7n2bw", "mikeejaylovessoul", "soul"),
]

def cavar(a):
    cid, nombre, gen = a
    cmd = [YT, "--flat-playlist", "--no-warnings", "-q", "--ignore-errors",
           "-I", "1:%d" % TOPE, "--print",
           "%%(id)s%s%%(title)s%s%%(duration)s%s%%(view_count)s" % (SEP, SEP, SEP),
           "https://www.youtube.com/channel/%s/videos" % cid]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=900)
    except subprocess.TimeoutExpired:
        print("  TIMEOUT %s" % nombre, flush=True)
        return {}
    got = {}
    for ln in r.stdout.splitlines():
        c = ln.split(SEP)
        if len(c) < 4 or len(c[0]) != 11:
            continue
        got[c[0]] = {"title": c[1], "uploader": nombre, "gen_canal": gen,
                     "dur": int(c[2]) if c[2].isdigit() else None,
                     "views": int(c[3]) if c[3].isdigit() else None}
    print("  %-34s %5d  [%s]" % (nombre, len(got), gen), flush=True)
    return got

pool = {}
with ThreadPoolExecutor(max_workers=5) as ex:
    for got in ex.map(cavar, CANALES):
        pool.update(got)
json.dump(pool, open(os.path.join(HERE, "demo_cavado.json"), "w", encoding="utf-8"),
          ensure_ascii=False)
print("\nTOTAL cavado: %d" % len(pool))
