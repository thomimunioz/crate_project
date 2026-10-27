# -*- coding: utf-8 -*-
"""Lista las 5 playlists curadas de Thomas para revisar si hay temas mal
catalogados (en la lista equivocada). yt-dlp flat = 0 quota."""
import json, os, subprocess
from concurrent.futures import ThreadPoolExecutor
YT = r"G:\Thomi - Mi Carpeta\crate_project\backend\.venv\Scripts\yt-dlp.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
SEP = chr(92) + "t"

PL = [
 ("PLPusvOhq-JPi9Wk0VjeK1O6XmjXrPOic6", "80s",     "quiet storm / slow jams / R&B 84-92"),
 ("PLPusvOhq-JPgdIait6bWewR3MLtRq8iqN", "soul",    "soul 70s, sweet/Philly/deep, 45s"),
 ("PLPusvOhq-JPihX79U16l6hEUj2-Z8_gDn", "rnb",     "R&B 77-92, quiet storm, smooth soul"),
 ("PLPusvOhq-JPiFC4DHYiwFjxHjsaBzHbvP", "citypop", "city pop japones 76-88"),
 ("PLPusvOhq-JPhfsRdVEt6UQnns3ofOqN-_", "fusion",  "jazz fusion mellow 74-90"),
 # sumadas el 27-oct
 ("PLPusvOhq-JPgcGVTjVA55v3aZUhzjfQhk", "piano",   "PIANO SAMPLES"),
 ("PLPusvOhq-JPhnLyNZ54450b_7WWWmBATu", "dark",    "DARK SAMPLES"),
 ("PLPusvOhq-JPh9daXD7V4L2-kVeQGLxiPr", "folk",    "FOLK SAMPLES"),
]

def listar(p):
    pid, slug, desc = p
    cmd = [YT, "--flat-playlist", "--no-warnings", "-q", "--ignore-errors",
           "--print", "%%(id)s%s%%(title)s%s%%(duration)s%s%%(view_count)s%s%%(uploader)s"
           % (SEP, SEP, SEP, SEP),
           "https://www.youtube.com/playlist?list=" + pid]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=300)
    except subprocess.TimeoutExpired:
        print("  TIMEOUT %s" % slug, flush=True)
        return slug, {}
    got = {}
    for ln in r.stdout.splitlines():
        c = ln.split(SEP)
        if len(c) < 5 or len(c[0]) != 11:
            continue
        got[c[0]] = {"title": c[1], "uploader": c[4],
                     "dur": int(c[2]) if c[2].isdigit() else None,
                     "views": int(c[3]) if c[3].isdigit() else None,
                     "listas": [slug]}
    print("  %-8s %3d temas   (%s)" % (slug, len(got), desc), flush=True)
    return slug, got

todo = {}
with ThreadPoolExecutor(max_workers=5) as ex:
    for slug, got in ex.map(listar, PL):
        for k, v in got.items():
            if k in todo:                       # el mismo video en dos listas
                todo[k]["listas"] += v["listas"]
            else:
                todo[k] = v
json.dump(todo, open(os.path.join(HERE, "pl_pool.json"), "w", encoding="utf-8"),
          ensure_ascii=False)
print("\nTOTAL en las 5 listas: %d" % len(todo))
