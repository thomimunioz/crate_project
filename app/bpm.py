"""Mide BPM/key de videos de YouTube con el DSP del backend de CRATE.
Uso: python bpm.py <videoId> [...]  → una línea JSON por video. Cachea en bpm_cache.json.
Receta que funciona en esta máquina: bajar bestaudio entero con yt-dlp (--js-runtimes node),
recortar 45 s desde el segundo 60 con ffmpeg a WAV mono 22050, y pasarle eso a Librosa.
"""
import json, sys, os, uuid, warnings, subprocess, time
warnings.filterwarnings("ignore")
os.chdir(r"G:\Thomi - Mi Carpeta\crate_project\backend")
sys.path.insert(0, r"G:\Thomi - Mi Carpeta\crate_project\backend")
import librosa
from app.dsp import _estimate_bpm, _estimate_key

YT = r"G:\Thomi - Mi Carpeta\crate_project\backend\.venv\Scripts\yt-dlp.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "bpm_cache.json")
TMP = os.path.join(HERE, "tmp_audio")
os.makedirs(TMP, exist_ok=True)


def measure(vid: str) -> dict:
    base = os.path.join(TMP, uuid.uuid4().hex)
    path = None
    try:
        r = subprocess.run([YT, "-f", "bestaudio/best", "--js-runtimes", "node", "--no-warnings", "-q",
                            "--no-playlist", "--print", "after_move:filepath", "--print", "after_move:%(duration)s",
                            "-o", base + ".%(ext)s", f"https://www.youtube.com/watch?v={vid}"],
                           capture_output=True, text=True, encoding="utf-8", timeout=240)
        lines = [l for l in r.stdout.splitlines() if l.strip()]
        if r.returncode != 0 or len(lines) < 2:
            raise RuntimeError((r.stderr.strip().splitlines() or ["yt-dlp falló"])[-1][:150])
        path, dur = lines[0].strip(), float(lines[1] or 0)
        offset = 60.0 if dur > 150 else max(0.0, dur * 0.2)
        wav = base + ".wav"
        subprocess.run(["ffmpeg", "-v", "quiet", "-y", "-ss", str(offset), "-t", "45", "-i", path,
                        "-ac", "1", "-ar", "22050", wav], check=True, timeout=120)
        y, sr = librosa.load(wav, sr=22050, mono=True)
        b, k = _estimate_bpm(y, sr), _estimate_key(y, sr)
        return {"bpm": round(b.value, 1), "bpm_conf": round(b.confidence, 2),
                "key": k.value, "key_conf": round(k.confidence, 2), "dur": int(dur)}
    finally:
        for f in (path, base + ".wav"):
            if f and os.path.exists(f):
                try: os.remove(f)
                except OSError: pass


def load():
    try: return json.load(open(CACHE, encoding="utf-8"))
    except Exception: return {}


for vid in [v for v in sys.argv[1:] if v]:
    cache = load()
    if vid in cache and "error" not in cache[vid]:
        print(json.dumps({"id": vid, **cache[vid], "cached": True}), flush=True)
        continue
    out = None
    for intento in range(3):
        try:
            out = measure(vid); break
        except Exception as e:  # noqa: BLE001
            out = {"error": str(e)[:160]}
            time.sleep(2 + intento * 3)
    cache = load()
    cache[vid] = out
    json.dump(cache, open(CACHE, "w", encoding="utf-8"))
    print(json.dumps({"id": vid, **out}), flush=True)
