# -*- coding: utf-8 -*-
"""Los discos que YA samplearon los productores que le gustan a Thomas.
La idea no es el corte que usaron: son los HERMANOS del mismo disco, que
siguen vírgenes. ytsearch de yt-dlp = 0 quota."""
import json, os, subprocess
from concurrent.futures import ThreadPoolExecutor
YT = r"G:\Thomi - Mi Carpeta\crate_project\backend\.venv\Scripts\yt-dlp.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
SEP = chr(92) + "t"

# (artista, año aprox, quién lo sampleó, escuela)
SEMILLAS = [
 ("Faith Hope & Charity",1978,"Nicholas Craven","sweet_soul"),
 ("Zingara",1981,"Nicholas Craven","sweet_soul"),
 ("Sound Experience",1974,"Nicholas Craven","sweet_soul"),
 ("The Raes",1978,"Nicholas Craven","sweet_soul"),
 ("The Futures",1978,"Nicholas Craven","sweet_soul"),
 ("Miquel Brown",1978,"Nicholas Craven","sweet_soul"),
 ("Diann Franklin",1981,"Knxwledge","modern_soul"),
 ("Gloria Scott",1974,"Knxwledge","sweet_soul"),
 ("Prince Harold",1966,"Knxwledge","deep_soul"),
 ("Odyssey 5",1974,"Knxwledge","sweet_soul"),
 ("Jorge Dalto",1976,"Knxwledge","latin_jazz"),
 ("Wendy Saddington",1971,"Knxwledge","psych_soul"),
 ("Monk Higgins",1975,"Camoflauge Monk","soul_jazz"),
 ("Derrick Erni",0,"Camoflauge Monk","library"),
 ("Eugene Record",1977,"Beat Butcha","sweet_soul"),
 ("Frank Cunimondo Trio",1972,"Beat Butcha","jazz"),
 ("Sweet Thursday",1969,"Beat Butcha","folk_rock"),
 ("Lesiman",1975,"Beat Butcha","library_ita"),
 ("John Fiddy",1979,"Daringer","library_euro"),
 ("Michel Colombier",1971,"Daringer","library_fra"),
 ("Thijs Van Leer",1972,"Daringer","library_ned"),
 ("Howard Lemon Singers",1973,"Daringer","gospel"),
 ("Gianni Marchetti",1973,"Camoflauge Monk","library_ita"),
 ("Francois de Roubaix",1971,"Camoflauge Monk","library_fra"),
 ("Zdzislawa Sosnicka",1974,"Camoflauge Monk","este"),
 ("Stan Tracey",1965,"Camoflauge Monk","jazz_uk"),
 ("Ian Carr Nucleus",1972,"Alchemist","jazz_uk"),
 ("Dave Greenslade",1979,"Alchemist","prog_uk"),
 ("Sergei Manukjan",1989,"Alchemist","este"),
 ("Svika Pick",1980,"Alchemist","israel"),
 ("Cem Karaca",1974,"Daringer","anadolu"),
 ("Riff Raff",1974,"Alchemist","jazz_rock"),
]

def buscar(s):
    artista, anio, quien, escuela = s
    q = f"ytsearch30:{artista} {anio if anio else ''}".strip()
    cmd = [YT, "--flat-playlist", "--no-warnings", "-q", "--ignore-errors",
           "--print", f"%(id)s{SEP}%(title)s{SEP}%(duration)s{SEP}%(view_count)s{SEP}%(uploader)s", q]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=180)
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT {artista}", flush=True); return {}
    got = {}
    for ln in r.stdout.splitlines():
        p = ln.split(SEP)
        if len(p) < 5 or len(p[0]) != 11: continue
        got[p[0]] = {"title": p[1], "uploader": p[4],
                     "dur": int(p[2]) if p[2].isdigit() else None,
                     "views": int(p[3]) if p[3].isdigit() else None,
                     "semilla": artista, "quien": quien, "escuela": escuela}
    print(f"  {artista}: {len(got)}", flush=True)
    return got

pool = {}
with ThreadPoolExecutor(max_workers=6) as ex:
    for got in ex.map(buscar, SEMILLAS):
        for k, v in got.items(): pool.setdefault(k, v)
json.dump(pool, open(os.path.join(HERE, "ws_semillas.json"), "w", encoding="utf-8"), ensure_ascii=False)
print(f"\nTOTAL hermanos encontrados: {len(pool)}")
