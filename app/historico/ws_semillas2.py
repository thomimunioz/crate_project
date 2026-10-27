# -*- coding: utf-8 -*-
"""2da ronda de semillas: SOLO del palo que pidio Thomas (rap grimy / drumless).
Roc Marciano, Benny, Conway, Estee Nack, Al.Divino, Vinyltracker/Cerounno.
Nada de trap ni de mainstream."""
import json, os, subprocess
from concurrent.futures import ThreadPoolExecutor
YT = r"G:\Thomi - Mi Carpeta\crate_project\backend\.venv\Scripts\yt-dlp.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
SEP = chr(92) + "t"

# (artista fuente, anio, quien lo sampleo, escuela)
SEMILLAS = [
 # --- Roc Marciano (se produce a si mismo; ~300 samples) ---
 ("Ronnie McNeir", 1975, "Roc Marciano", "modern_soul"),
 ("The Holy Light Jr", 1974, "Roc Marciano", "gospel_soul"),
 ("Smoked Sugar", 1975, "Roc Marciano", "sweet_soul"),
 ("Astra Nova Orchestra", 1974, "Roc Marciano", "library"),
 ("Mighty Doug Haynes", 1974, "Roc Marciano", "deep_soul"),
 ("Turner Bros", 1974, "Roc Marciano", "sweet_soul"),
 ("Anna German", 1975, "Roc Marciano", "este"),
 ("I Nomadi", 1972, "Roc Marciano", "italia"),
 # --- Benny the Butcher / Conway (Daringer, Beat Butcha, Camoflauge Monk) ---
 ("Bernard Callais", 1971, "Benny the Butcher", "library_fra"),
 ("Greg Perry", 1977, "Benny the Butcher", "sweet_soul"),
 ("Timo Laine", 1978, "Conway the Machine", "modern_soul"),
 ("Yasuko Kawashima", 1976, "Benny the Butcher", "japon"),
 # --- Estee Nack / Al.Divino ---
 ("A.A.B.B.", 1975, "Estee Nack", "funk_soul"),
 ("Full Speed", 1979, "Al.Divino", "sweet_soul"),
 # --- escuela de Conductor Williams ---
 ("Billy Cobham", 1976, "Conductor Williams", "fusion"),
 ("Bread", 1972, "Conductor Williams", "soft_rock"),
 # --- Daringer (del cruce anterior) ---
 ("Howard Lemon Singers", 1973, "Daringer", "gospel"),
]

def buscar(s):
    artista, anio, quien, escuela = s
    q = "ytsearch30:%s %s" % (artista, anio or "")
    cmd = [YT, "--flat-playlist", "--no-warnings", "-q", "--ignore-errors",
           "--print", "%%(id)s%s%%(title)s%s%%(duration)s%s%%(view_count)s%s%%(uploader)s"
           % (SEP, SEP, SEP, SEP), q.strip()]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=180)
    except subprocess.TimeoutExpired:
        print("  TIMEOUT %s" % artista, flush=True)
        return {}
    got = {}
    for ln in r.stdout.splitlines():
        p = ln.split(SEP)
        if len(p) < 5 or len(p[0]) != 11:
            continue
        got[p[0]] = {"title": p[1], "uploader": p[4],
                     "dur": int(p[2]) if p[2].isdigit() else None,
                     "views": int(p[3]) if p[3].isdigit() else None,
                     "semilla": artista, "quien": quien, "escuela": escuela}
    print("  %s: %d" % (artista, len(got)), flush=True)
    return got

pool = {}
with ThreadPoolExecutor(max_workers=6) as ex:
    for got in ex.map(buscar, SEMILLAS):
        for k, v in got.items():
            pool.setdefault(k, v)
json.dump(pool, open(os.path.join(HERE, "ws_semillas2.json"), "w", encoding="utf-8"),
          ensure_ascii=False)
print("\nTOTAL hermanos ronda 2: %d" % len(pool))
