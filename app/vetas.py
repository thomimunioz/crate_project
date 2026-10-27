"""Cava los canales curadores que YA le rindieron a Thomas. Sin quota (yt-dlp flat)."""
import json, os, subprocess
from concurrent.futures import ThreadPoolExecutor
YT = r"G:\Thomi - Mi Carpeta\crate_project\backend\.venv\Scripts\yt-dlp.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "vetas_pool.json")

# (channel_id, nombre, cuántos pedir) — priorizados por hit rate medido y por género
CANALES = [
  ("UCY8_y20lxQhhBe8GZl5A9rw", "Music for empty rooms", 600),      # 6/41 — etiqueta país+género+año
  ("UC47qc6t2RelhfvI-OjgIY2A", "Rare Samples & Songs Oleg Tsoy", 600),  # 4/44
  ("UCE-O0L9EzmoEcM69E3QjGTg", "TheRAREGROOVEMAN", 500),            # 3/13 — soul 70s
  ("UCTFuQaZ4XJ0jQO1MJ4dYFXw", "si", 400),                          # 3/3 — modern soul con Discogs
  ("UCiMAhn-OD_XA8T_reQMcwMA", "Soultwinz", 400),                   # 2/16 — 45s de soul
  ("UC546_voUGtgQr5LmtWV-4pQ", "Winta Groove", 300),                # 2/2
  ("UCv5OAW45h67CJEY6kJLyisg", "André Navarro II", 500),            # city pop + library japonés
  ("UC1r_Q42GyLb2I1mL0L1Mxqw", "skeenery", 300),                    # 1/11 — modern soul
  ("UCYPltVawiS_dVsyv13hERgw", "Neglected Trax", 300),              # 1/8
  ("UCr79VNMYJiZCIUrBt9le6kQ", "JazzManDean", 400),                 # fusion
  ("UC4rdJibQ4NfeJxGbg4rvNxw", "ants kask", 300),                   # city pop japonés
  ("UCXV_UkAxldqySLJ-FNqFnCA", "Casen Fike", 300),                  # soul samples
  ("UC2xLCkq2twf355YoQggRTyQ", "foreal", 300),
  ("UCEiSkaHC2pejVpfC90jeANg", "Krem Soulz", 300),
  ("UCyTbMneufohqr7-XNydLg0w", "secondscene", 200),
  ("UCAE-UJvklqnSs96vmdu6vQw", "DJ Vinyl Goblin", 200),
  ("UC8miJX57wgdexh0Wb7z8wBA", "Five Special Records", 200),
  ("UCkjBeNtQtmhGOkEegI2W5_g", "aaappleknocker", 300),
  ("UC8U4Px_RbJat4_4LKJ7n2bw", "mikeejaylovessoul", 300),
  ("UCEfDmBvn1UduuZ84xHB09lQ", "Athens of The North", 300),
  ("UCP-R7czth3VnJZL_lwA829Q", "Cool Breeze", 300),
  ("UCwF7X0M0RH3ryBGgy8QiDCA", "On the Rocks Records", 200),
  ("UCekevJPGTZ44nn_i4SWJDIw", "The Voice of Anton", 300),
  ("UCEm5THU0Fg1hOYxgONkTmug", "Elwood P. Dowd", 200),
  ("UCnVk2SYJ3ZIhp0FCB9a1EGg", "JefferyBeats", 200),
  ("UCL8EjPRV5WxrpzU4vn7j8eQ", "BigPeter1027 Real Music Channel", 400),
  # curadores que aparecieron en las entregas de la Sierra / LatAm
  ("@VinyleArcheologie", "Vinyle Archéologie", 400),
  ("@TeenenTander", "Teen en Tander", 400),
  ("@dustybreaks", "Dusty Breaks", 300),
]

def listar(arg):
    cid, nombre, n = arg
    url = f"https://www.youtube.com/{cid}/videos" if cid.startswith("@") else f"https://www.youtube.com/channel/{cid}/videos"
    try:
        r = subprocess.run([YT, "--flat-playlist", "--no-warnings", "-I", f"1:{n}", "--print",
                            "%(id)s|||%(title)s|||%(duration)s|||%(view_count)s", url],
                           capture_output=True, text=True, encoding="utf-8", timeout=600)
        out = []
        for l in r.stdout.splitlines():
            p = l.split("|||")
            if len(p) < 4 or not p[0]: continue
            out.append({"id": p[0], "title": p[1], "uploader": nombre,
                        "dur": int(float(p[2])) if p[2] not in ("NA", "") else None,
                        "views": int(float(p[3])) if p[3] not in ("NA", "") else None})
        return nombre, out
    except Exception as e:  # noqa: BLE001
        return nombre, []

pool = {}
with ThreadPoolExecutor(5) as ex:
    for nombre, items in ex.map(listar, CANALES):
        print(f"{nombre}: {len(items)}", flush=True)
        for it in items:
            pool.setdefault(it["id"], it)
json.dump(pool, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("TOTAL:", len(pool), "→", OUT)
