"""Año (℗ de la descripción) y snippet para IDs de YouTube. Sin quota. Cachea en meta_cache.json."""
import json, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
YT = r"G:\Thomi - Mi Carpeta\crate_project\backend\.venv\Scripts\yt-dlp.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "meta_cache.json")
try:
    cache = json.load(open(CACHE, encoding="utf-8"))
except Exception:
    cache = {}


def fetch(vid):
    if vid in cache and "error" not in cache[vid]:
        return vid, cache[vid]
    try:
        out = subprocess.run([YT, "--skip-download", "--no-warnings", "--js-runtimes", "node", "--print",
                              "%(upload_date)s|||%(uploader)s|||%(title)s|||%(view_count)s|||%(description)s",
                              f"https://www.youtube.com/watch?v={vid}"],
                             capture_output=True, text=True, encoding="utf-8", timeout=90).stdout
    except Exception as e:  # noqa: BLE001
        return vid, {"error": str(e)[:120]}
    parts = out.split("|||", 4)
    if len(parts) < 5:
        return vid, {"error": "sin metadata"}
    up, uploader, title, views, desc = parts
    m = re.search(r"[℗©]\s*(\d{4})", desc) or re.search(r"\b(19[4-9]\d|20[0-2]\d)\b", desc + " " + title)
    return vid, {"year": m.group(1) if m else None,
                 "phonogram": bool(re.search(r"[℗©]\s*\d{4}", desc)),
                 "views": int(views) if views.strip().isdigit() else None,
                 "uploader": uploader.strip(), "title": title.strip(),
                 "desc": re.sub(r"\s+", " ", desc)[:200]}


ids = [v for v in sys.argv[1:] if v]
with ThreadPoolExecutor(6) as ex:
    for vid, info in ex.map(fetch, ids):
        cache[vid] = info
        print(json.dumps({"id": vid, **info}, ensure_ascii=False)[:160], flush=True)
json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
print("total en cache:", len(cache))
