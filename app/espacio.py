# -*- coding: utf-8 -*-
"""Mide el ESPACIO INSTRUMENTAL de un tema: cuanto hay sin voz y donde.

Thomas, 24-oct-2026: "yo no necesito que la cancion lo loopee, pero si necesito
que haya espacio, si hay voces obvio eso pasa en la gran mayoria, pero lo
importante es q no esten todo el pto tema cantando."

O sea: tener voz no descalifica. Lo que descalifica es cantar de punta a punta.
"voz" es su 3er motivo de rechazo (9 veces) y hasta ahora no lo medía.

ESTADO AL 24-oct-2026: NO FUNCIONA TODAVIA. NO USAR PARA RANKEAR.

Dos intentos, los dos fallidos:
  1. Heuristica con pyin (este archivo): daba "100% sin voz" hasta en un tema
     cantado de punta a punta. Dos bugs: pyin devuelve vprob entre 0.01 y 0.11
     (el que sirve es vflag, el booleano), y el suavizado borraba la deteccion
     dispersa. Corregido eso sigue sin separar.
  2. Mid/side (midside.py): mejor — en los Chi-Lites encuentra la intro de 17 s,
     que es real — pero usa un umbral por percentil, o sea auto-referencial:
     siempre marca ~45% como voz. Y el bajo y el bombo tambien van al centro,
     asi que un instrumental puede dar "centro dominante" sin que cante nadie.

El camino correcto es separacion de fuentes pre-entrenada (Demucs o Spleeter):
aisla la pista vocal de verdad y el hueco se lee midiendo su energia. Pesa
(PyTorch) y tarda ~1-2 min por tema en CPU, pero es exactamente la Capa 2
opt-in que CRATE define.

Falta ademas la validacion: medir contra los 9 rechazos por "voz" de Thomas y
sus guardados. No se pudo hacer porque YouTube corto las descargas por volumen.

Uso: python espacio.py <id> [...]  -> cachea en espacio_cache.json
"""
import json, sys, os, uuid, warnings, subprocess, time
warnings.filterwarnings("ignore")
os.chdir(r"G:\Thomi - Mi Carpeta\crate_project\backend")
sys.path.insert(0, r"G:\Thomi - Mi Carpeta\crate_project\backend")
import numpy as np
import librosa

YT = r"G:\Thomi - Mi Carpeta\crate_project\backend\.venv\Scripts\yt-dlp.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "espacio_cache.json")
TMP = os.path.join(HERE, "tmp_audio")
os.makedirs(TMP, exist_ok=True)
SR, HOP = 22050, 512
VENTANA = 150          # segundos de audio a analizar (desde el arranque)


def voz_por_frame(y, sr):
    """Devuelve un bool por frame: hay voz o no."""
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=HOP))
    arm, _ = librosa.decompose.hpss(S)
    f = librosa.fft_frequencies(sr=sr, n_fft=2048)

    banda = (f >= 200) & (f <= 3500)
    e_voz = arm[banda].sum(axis=0)
    e_tot = arm.sum(axis=0) + 1e-9
    ratio = e_voz / e_tot                     # cuanta energia cae en banda vocal

    # F0 y su micro-variacion: la voz nunca queda quieta, un teclado si
    # OJO: pyin devuelve vprob casi siempre entre 0.01 y 0.11, nunca alto.
    # El que sirve es vflag (el booleano voiced/unvoiced).
    f0, vflag, _ = librosa.pyin(
        y, fmin=80, fmax=1000, sr=sr, hop_length=HOP,
        frame_length=2048, fill_na=np.nan)
    n = min(len(ratio), len(f0))
    ratio, f0, vflag = ratio[:n], f0[:n], vflag[:n].astype(bool)

    cents = np.full(n, np.nan)
    ok = ~np.isnan(f0)
    cents[ok] = 1200 * np.log2(f0[ok] / 55.0)
    vib = np.full(n, 0.0)
    W = 9
    for i in range(n):
        a, b = max(0, i - W), min(n, i + W)
        seg = cents[a:b][~np.isnan(cents[a:b])]
        if len(seg) >= 5:
            vib[i] = float(np.std(seg))

    rms = librosa.feature.rms(y=y, hop_length=HOP)[0][:n]
    fuerte = rms > (np.percentile(rms, 30) + 1e-9)

    # voz = pitch presente (vflag) + energia concentrada en banda vocal +
    # micro-variacion propia de una garganta + no es silencio.
    # Umbrales calibrados mirando valores reales: en un tema cantado de punta a
    # punta el ratio mediano ronda 0.77; en uno instrumental, 0.48-0.65.
    voz = vflag & (ratio > 0.62) & (vib > 8) & (vib < 260) & fuerte
    # suavizado: ignora parpadeos de menos de ~0.5 s en ambos sentidos
    k = 21
    sm = np.convolve(voz.astype(float), np.ones(k) / k, mode="same") > 0.40
    return sm, n


def huecos(voz, sr):
    """Tramos continuos SIN voz, en segundos."""
    seg, ini = [], None
    for i, v in enumerate(voz):
        if not v and ini is None:
            ini = i
        elif v and ini is not None:
            seg.append((ini, i)); ini = None
    if ini is not None:
        seg.append((ini, len(voz)))
    t = HOP / sr
    return [(a * t, (b - a) * t) for a, b in seg]


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
        wav = base + ".wav"
        subprocess.run(["ffmpeg", "-v", "quiet", "-y", "-t", str(VENTANA), "-i", path,
                        "-ac", "1", "-ar", str(SR), wav], check=True, timeout=140)
        y, sr = librosa.load(wav, sr=SR, mono=True)
        voz, n = voz_por_frame(y, sr)
        hs = huecos(voz, sr)
        analizado = n * HOP / sr
        mayor = max(hs, key=lambda h: h[1]) if hs else (0.0, 0.0)
        intro = hs[0][1] if hs and hs[0][0] < 1.0 else 0.0
        return {"dur": int(dur), "analizado": round(analizado, 1),
                "sin_voz_pct": round(100.0 * float((~voz).mean()), 1),
                "hueco_max_s": round(mayor[1], 1),
                "hueco_max_en": round(mayor[0], 1),
                "intro_s": round(intro, 1),
                "huecos_8s": sum(1 for _, d in hs if d >= 8.0)}
    finally:
        for f in (path, base + ".wav"):
            if f and os.path.exists(f):
                try: os.remove(f)
                except OSError: pass


def load():
    try: return json.load(open(CACHE, encoding="utf-8"))
    except Exception: return {}


if __name__ == "__main__":
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
