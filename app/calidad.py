# -*- coding: utf-8 -*-
"""Mide CALIDAD DE RIP, que es el 2do motivo de rechazo de Thomas ("rip", 6 veces).

Su observacion del 24-oct: "en las listas de soul lo de las visitas te mata xq
los vinyls q encontras suenan para el orto MAL". Tiene razon: premiar pocas
visitas es premiar rips caseros de vinilo rayado.

A diferencia de "plano" o "efusivo", esto SI deja huella fisica medible:
  * corte de banda: un MP3 de 128k muere en ~16 kHz, un rip decente llega a 20+
  * ruido de superficie: los clicks del vinilo son transitorios de banda ancha
  * clipping: picos pegados a 0 dBFS = rip saturado
  * ruido de fondo: el piso de ruido en los silencios
Uso: python calidad.py <id> [...]  -> cachea en calidad_cache.json
"""
import json, sys, os, uuid, warnings, subprocess, time
warnings.filterwarnings("ignore")
os.chdir(r"G:\Thomi - Mi Carpeta\crate_project\backend")
sys.path.insert(0, r"G:\Thomi - Mi Carpeta\crate_project\backend")
import numpy as np
import librosa

YT = r"G:\Thomi - Mi Carpeta\crate_project\backend\.venv\Scripts\yt-dlp.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "calidad_cache.json")
TMP = os.path.join(HERE, "tmp_audio")
os.makedirs(TMP, exist_ok=True)
SR = 44100          # hace falta sr alto: a 22050 no se ve el corte de banda


def features(y, sr):
    S = np.abs(librosa.stft(y, n_fft=4096))
    f = librosa.fft_frequencies(sr=sr, n_fft=4096)
    esp = S.mean(axis=1)
    tot = esp.sum() + 1e-9

    # corte de banda: la frecuencia por encima de la cual queda <0.15% de energia
    acum = np.cumsum(esp) / tot
    corte = float(f[np.searchsorted(acum, 0.9985)])

    # cuanta energia hay arriba de 16 kHz (un MP3 berreta: casi cero)
    alto = float(esp[f >= 16000].sum() / tot)

    # clipping: muestras pegadas al tope
    clip = float(np.mean(np.abs(y) > 0.985))

    # ruido de superficie: percusivo de banda ancha sobre el residuo armonico
    arm, perc = librosa.decompose.hpss(S)
    hf = f >= 8000
    crackle = float(perc[hf].mean() / (arm[hf].mean() + 1e-9))

    # piso de ruido: percentil 5 de la energia RMS por frame
    rms = librosa.feature.rms(y=y)[0]
    piso = float(np.percentile(rms, 5) / (np.percentile(rms, 95) + 1e-9))

    # rango dinamico: lo que Thomas llama "plano" cuando es muy chico
    din = float(np.percentile(rms, 95) - np.percentile(rms, 10))
    return {"corte_hz": round(corte), "energia_agudos": round(alto, 5),
            "clipping": round(clip, 5), "crackle": round(crackle, 4),
            "piso_ruido": round(piso, 4), "rango_dinamico": round(din, 4)}


def medir(vid):
    base = os.path.join(TMP, uuid.uuid4().hex)
    path = None
    try:
        r = subprocess.run(
            [YT, "-f", "bestaudio/best", "--js-runtimes", "node", "--no-warnings", "-q",
             "--no-playlist", "--print", "after_move:filepath",
             "--print", "after_move:%(duration)s", "-o", base + ".%(ext)s",
             "https://www.youtube.com/watch?v=" + vid],
            capture_output=True, text=True, encoding="utf-8", timeout=240)
        ln = [l for l in r.stdout.splitlines() if l.strip()]
        if r.returncode != 0 or len(ln) < 2:
            raise RuntimeError((r.stderr.strip().splitlines() or ["yt-dlp fallo"])[-1][:140])
        path, dur = ln[0].strip(), float(ln[1] or 0)
        off = 60.0 if dur > 150 else max(0.0, dur * 0.2)
        wav = base + ".wav"
        subprocess.run(["ffmpeg", "-v", "quiet", "-y", "-ss", str(off), "-t", "40",
                        "-i", path, "-ac", "1", "-ar", str(SR), wav],
                       check=True, timeout=120)
        y, sr = librosa.load(wav, sr=SR, mono=True)
        return features(y, sr)
    finally:
        for f in (path, base + ".wav"):
            if f and os.path.exists(f):
                try: os.remove(f)
                except OSError: pass


def load():
    try: return json.load(open(CACHE, encoding="utf-8"))
    except Exception: return {}


for vid in [v for v in sys.argv[1:] if v]:
    c = load()
    if vid in c and "error" not in c[vid]:
        print(json.dumps({"id": vid, **c[vid], "cached": True}), flush=True)
        continue
    out = None
    for i in range(3):
        try:
            out = medir(vid); break
        except Exception as e:  # noqa: BLE001
            out = {"error": str(e)[:150]}
            time.sleep(2 + i * 3)
    c = load(); c[vid] = out
    json.dump(c, open(CACHE, "w", encoding="utf-8"))
    print(json.dumps({"id": vid, **out}), flush=True)
