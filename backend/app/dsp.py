"""
DSP: baja el audio con yt-dlp, recorta la ventana con ffmpeg y estima BPM + tonalidad
con Librosa. Siempre con confidence, siempre con las alternativas a la vista.

Cómo se baja (lo que anduvo el 19-sep, ver .claude/agents/dsp-analyst.md):
- `bestaudio` ENTERO con el downloader nativo de yt-dlp a `tmp/`. Recortar en la descarga
  (`download_ranges`) delega en ffmpeg y YouTube responde 403; bajar entero son ~4 MB y ~2 s.
- Después, uno o más recortes con ffmpeg a WAV mono 22050 (librosa lo carga en ~1 s; el
  webm/opus vía audioread tardaba 18 s). Una descarga, varios usos: BPM/key leen su
  ventana, la huella acústica lee desde el segundo 0.
- Todo (original + recortes) se borra en `finally`, falle lo que falle. La descarga es
  temporal e interna: nunca se sirve ni se guarda audio.

Cómo se decide el BPM: por EVIDENCIA de audio, sin prior de gusto. El backend devuelve el
candidato con más support y todos los demás (`alternatives`) con el suyo; si el cliente
quiere plegar el tempo a su rango (affinity), lo hace él y lo dice en el Why this.
"""
from __future__ import annotations

import logging
import os
import subprocess
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

import librosa
import numpy as np
from yt_dlp import YoutubeDL

from . import ytdl
from .config import settings
from .models import AnalyzeResult, BpmAlternative, BpmResult, BpmWindow, KeyResult

log = logging.getLogger("crate.dsp")

PITCH_CLASSES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Perfiles Krumhansl-Kessler para estimación de tonalidad
KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

# Los recortes salen siempre así: mono a 22050. Todo el DSP asume este sr.
SR = 22050
_HOP = 512
_N_FFT = 2048
_N_MELS = 128


# =============================================================================== descarga


@dataclass(frozen=True)
class Fragment:
    """Un recorte (WAV mono 22050) en disco + lo que sabemos del track del que salió."""
    path: str
    start: float
    seconds: int
    source_duration: float | None  # duración del track completo, según la fuente


@dataclass
class Downloaded:
    """El audio completo bajado a tmp (temporal). `cut()` saca recortes; el context manager
    que lo creó borra el original y todos los recortes al salir."""
    path: str
    duration: float | None
    _base: str
    _cuts: list[str] = field(default_factory=list)

    def cut(self, start: float, seconds: int) -> Fragment:
        """Recorta [start, start+seconds) a WAV mono 22050 con ffmpeg. La ventana se acomoda
        para no pasarse del final del track."""
        start, seconds = clamp_window(start, seconds, self.duration)
        wav = f"{self._base}.{len(self._cuts)}.wav"
        self._cuts.append(wav)
        ffmpeg = ytdl.ffmpeg_path()
        if not ffmpeg:
            raise ytdl.ToolchainError(ytdl.toolchain()["ffmpeg"]["problem"])
        cmd = [
            ffmpeg, "-v", "error", "-nostdin", "-y",
            "-ss", f"{start:.3f}", "-t", str(seconds), "-i", self.path,
            "-vn", "-ac", "1", "-ar", str(SR), "-f", "wav", wav,
        ]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=settings.ffmpeg_timeout_sec,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"ffmpeg tardó más de {settings.ffmpeg_timeout_sec}s recortando") from exc
        if proc.returncode != 0 or not os.path.exists(wav):
            raise RuntimeError(f"ffmpeg falló ({proc.returncode}): {proc.stderr.strip()[:300]}")
        return Fragment(path=wav, start=start, seconds=seconds, source_duration=self.duration)


def smart_start(duration: float | None) -> float:
    """Dónde arranca la ventana de BPM/key si el cliente no lo dice: a los 60 s (pasada la
    intro) o, en tracks de <= 150 s, al 20%. Es lo que se midió sobre 247 temas el 19-sep."""
    if duration and duration > 150:
        return 60.0
    return max(0.0, float(duration or 0.0) * 0.2)


def clamp_window(start: float, seconds: int, duration: float | None) -> tuple[float, int]:
    """Acomoda la ventana adentro del track: si no entra entera, corre el arranque atrás;
    si el track es más corto que la ventana, la achica."""
    start = max(0.0, float(start))
    seconds = max(1, int(seconds))
    if duration and duration > 0:
        if seconds > duration:
            seconds = max(1, int(duration))
        if start + seconds > duration:
            start = max(0.0, duration - seconds)
    return start, seconds


def _downloaded_path(info: dict, ydl: YoutubeDL) -> str:
    """El nombre real puede no ser el previsto (remux/merge): yt-dlp lo deja en requested_downloads."""
    for entry in info.get("requested_downloads") or []:
        path = entry.get("filepath")
        if path and os.path.exists(path):
            return path
    return ydl.prepare_filename(info)


@contextmanager
def download_audio(url: str) -> Iterator[Downloaded]:
    """
    Baja `bestaudio` entero a `tmp/` (descarga temporal) y garantiza el borrado del original
    y de cada recorte, falle lo que falle. Chequea el toolchain ANTES de tocar la red
    (`ToolchainError` -> 503). Los 403 esporádicos se reintentan (`ytdl.with_retry`).

    `url` se normaliza a UN video (`ytdl.video_url`: id, youtu.be, watch?v=) antes de
    llamar a yt-dlp: una URL de playlist pura no la frena `noplaylist` y bajaría la lista
    entera al mismo archivo antes de fallar. Lo que no sea un video -> `InvalidUrl` (400).
    """
    url = ytdl.video_url(url)
    ytdl.ensure_ready(ffmpeg=True)
    os.makedirs(settings.tmp_dir, exist_ok=True)
    uid = uuid.uuid4().hex
    base = os.path.join(settings.tmp_dir, uid)
    opts = ytdl.ydl_opts(format="bestaudio/best", outtmpl=base + ".%(ext)s")

    def _bajar() -> Downloaded:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True) or {}
            if info.get("_type") == "playlist":
                # No debería pasar con la URL canónica; red de seguridad, no un path normal.
                raise RuntimeError("yt-dlp devolvió una playlist para una URL de video")
            duration = info.get("duration")
            return Downloaded(
                path=_downloaded_path(info, ydl),
                duration=float(duration) if duration else None,
                _base=base,
            )

    try:
        audio = ytdl.with_retry(_bajar)
        # Bajó: si había un bot-check registrado, ya no vale (ver ytdl.youtube_block).
        ytdl.clear_block()
        yield audio
    finally:
        # Borrado por prefijo único (uuid): agarra el original, los recortes y cualquier
        # .part que haya quedado de una descarga cortada. Nunca toca archivos ajenos.
        try:
            for name in os.listdir(settings.tmp_dir):
                if name.startswith(uid):
                    try:
                        os.remove(os.path.join(settings.tmp_dir, name))
                    except OSError:
                        pass
        except OSError:
            pass


@contextmanager
def fragment(url: str, start: float | None, seconds: int) -> Iterator[Fragment]:
    """Atajo de un solo recorte: baja, corta `seconds` desde `start` (o desde `smart_start`)
    y borra al salir. Para dos ventanas (BPM + huella) usá `download_audio` + `cut`."""
    with download_audio(url) as audio:
        yield audio.cut(smart_start(audio.duration) if start is None else start, seconds)


# =============================================================================== features


def _logmel(y: np.ndarray, sr: int = SR) -> np.ndarray:
    """Mel-espectrograma en dB (128 bandas, n_fft 2048, hop 512). Se calcula UNA vez y de
    acá salen la envolvente de onset completa y las envolventes por banda."""
    S = librosa.feature.melspectrogram(y=y, sr=sr, n_fft=_N_FFT, hop_length=_HOP, n_mels=_N_MELS)
    return librosa.power_to_db(S)


def onset_from_logmel(S: np.ndarray, sr: int = SR, band: tuple[float, float] | None = None) -> np.ndarray:
    """Envolvente de onset (flux espectral positivo, promedio por banda) a partir del mel en dB.
    Sin `band` es exactamente `librosa.onset.onset_strength(y, sr, hop_length=512)`."""
    if band is not None:
        centers = librosa.mel_frequencies(n_mels=_N_MELS, fmin=0.0, fmax=sr / 2.0)
        mask = (centers >= band[0]) & (centers < band[1])
        if not mask.any():
            return np.zeros(S.shape[1], dtype=np.float32)
        S = S[mask]
    return librosa.onset.onset_strength(S=S, sr=sr, n_fft=_N_FFT, hop_length=_HOP).astype(np.float32)


# Bandas para el chequeo de backbeat: bombo abajo, caja (el "crack") arriba del cuerpo.
BAND_KICK = (30.0, 130.0)
BAND_SNARE = (1500.0, 6000.0)


def _onset_envelope(y: np.ndarray, sr: int = SR) -> np.ndarray:
    return librosa.onset.onset_strength(y=y, sr=sr, hop_length=_HOP).astype(np.float32)


# =============================================================================== BPM

# Método/versión del algoritmo de tempo. Subir cuando cambie la decisión: el cliente lo
# usa para saber qué análisis viejos vale la pena re-correr.
BPM_METHOD = "onset-ac/2"

# Dónde se buscan candidatos (picos de la autocorrelación y sus x0.5/x2). Es un rango
# perceptual, no de gusto: por debajo de ~50 o por encima de ~240 no se percibe un beat
# (Percival & Tzanetakis 2014 pliegan a 50-210). Medido: con 40 el candidato a la mitad
# (40-50 BPM) ganaba en 13 temas más; el gusto del usuario (58-115 hoy) queda en el cliente.
_CAND_MIN, _CAND_MAX = 50.0, 240.0
# Rango donde se pliega el candidato de respaldo de `librosa.feature.tempo` (solo se usa
# cuando la autocorrelación no tiene picos). 55 y no 60: un 58 real no se pliega a 116.
_BPM_MIN, _BPM_MAX = 55.0, 180.0
# Cuántos picos se toman como semilla y a qué distancia dos candidatos son el mismo.
_MAX_PEAKS = 5
_DEDUPE_TOL = 0.03


@dataclass(frozen=True)
class BpmParams:
    """Perillas de la decisión de tempo. Los defaults son los calibrados con
    `tools/bpm_calibrate.py` sobre el dataset del 19-sep. Ningún parámetro es un rango
    de gusto: son pesos de evidencia sobre la jerarquía métrica de la autocorrelación.

    Puntaje de un candidato con lag l (S = pico normalizado de la autocorrelación):
        score(l) = S(l) + sub_weight * S(l/2) - subsub_weight * S(l/4) + sup_weight * S(2l)
                   + backbeat_weight * backbeat(l)
    La idea, medida sobre 247 temas: en el beat real la subdivisión (l/2, la corchea) es
    casi tan fuerte como el beat y la sub-subdivisión (l/4) es débil; en el candidato al
    doble su subdivisión ya es la semicorchea (débil); en el candidato a la mitad, las dos
    subdivisiones son fuertes. La autocorrelación cruda sola es moneda al aire (45%)."""
    sub_weight: float = 1.0
    subsub_weight: float = 0.25
    sup_weight: float = 0.0
    # Quitar la media de la envolvente antes de autocorrelar (más rango dinámico en los picos).
    detrend: bool = True
    # Umbral de ambigüedad: segundo.score >= ambiguous_ratio x mejor.score -> ambiguous.
    # Calibrado: con 0.75 se marca el 48% de los temas y ahí caen el 76% de los errores;
    # lo que NO se marca acierta ~90%.
    ambiguous_ratio: float = 0.75
    # Peso del voto de backbeat por paridad (bombo y caja en beats opuestos). Medido: +7
    # temas sobre 247 (72% -> 75%) sin perder ninguno.
    backbeat_weight: float = 1.0


DEFAULT_PARAMS = BpmParams()


def _fold(bpm: float) -> float:
    """Lleva un tempo al rango [_BPM_MIN, _BPM_MAX] duplicando o partiendo por dos.
    Un tempo que no es un número positivo finito devuelve 0 (sin pulso): con 0 o inf los
    `while` no terminarían nunca."""
    if not np.isfinite(bpm) or bpm <= 0:
        return 0.0
    while bpm < _BPM_MIN:
        bpm *= 2
    while bpm > _BPM_MAX:
        bpm /= 2
    return bpm


def _lag_of(bpm: float, sr: int) -> float:
    return 60.0 * sr / (_HOP * bpm)


def _bpm_of(lag: float, sr: int) -> float:
    return 60.0 * sr / (_HOP * lag)


def _refine_peak(ac: np.ndarray, lag: int) -> tuple[float, float]:
    """Interpolación parabólica del máximo local en `lag` -> (lag refinado, valor del pico).
    Sin esto los tempos salen cuantizados a lags enteros (117.5 / 123 / 129.2 a hop 512)."""
    if lag <= 0 or lag >= ac.size - 1:
        return float(lag), (float(ac[lag]) if 0 <= lag < ac.size else 0.0)
    a, b, c = float(ac[lag - 1]), float(ac[lag]), float(ac[lag + 1])
    denom = a - 2.0 * b + c
    if abs(denom) < 1e-12:
        return float(lag), b
    delta = float(np.clip(0.5 * (a - c) / denom, -0.5, 0.5))
    return lag + delta, b - 0.25 * (a - c) * delta


def _interp(ac: np.ndarray, lag: float) -> float:
    """Valor de `ac` en un lag no entero (lineal)."""
    if lag <= 0 or lag >= ac.size - 1:
        return 0.0
    i = int(np.floor(lag))
    frac = lag - i
    return float(ac[i] * (1.0 - frac) + ac[i + 1] * frac)


def _peak_near(ac: np.ndarray, lag: float, tol: float = 0.025) -> tuple[float, float]:
    """El máximo local más alto a +-tol (relativo, mínimo +-1 lag) de `lag`, refinado.
    Si no hay máximo local en la vecindad, el valor interpolado en `lag` (evidencia floja)."""
    if ac.size < 3 or lag < 1:
        return lag, 0.0
    radius = max(1, int(round(lag * tol)))
    lo = max(1, int(np.floor(lag)) - radius)
    hi = min(ac.size - 2, int(np.ceil(lag)) + radius)
    best_lag, best_val = lag, -np.inf
    for i in range(lo, hi + 1):
        if ac[i] >= ac[i - 1] and ac[i] >= ac[i + 1]:
            l_ref, v = _refine_peak(ac, i)
            if v > best_val:
                best_lag, best_val = l_ref, v
    if best_val == -np.inf:
        return lag, _interp(ac, lag)
    return best_lag, float(best_val)


def _autocorr(onset: np.ndarray, sr: int, detrend: bool = False) -> np.ndarray:
    """Autocorrelación de la envolvente hasta 4x el lag del tempo más lento (para 2x/4x)."""
    sig = np.asarray(onset, dtype=np.float64)
    if detrend:
        sig = sig - sig.mean()
    max_lag = int(_lag_of(_CAND_MIN, sr) * 4) + 3
    return librosa.autocorrelate(sig, max_size=min(max_lag, sig.size)).astype(np.float64)


def _local_maxima(ac: np.ndarray, lag_lo: float, lag_hi: float) -> list[int]:
    idx = np.flatnonzero((ac[1:-1] > ac[:-2]) & (ac[1:-1] >= ac[2:])) + 1
    return [int(i) for i in idx if lag_lo <= i <= lag_hi]


def _best_phase(onset: np.ndarray, lag: float) -> int:
    """Fase (frame) donde cae el pulso de período `lag`: la que acumula más onset."""
    n = onset.size
    ph = np.floor(np.mod(np.arange(n), lag)).astype(int)
    nb = int(np.ceil(lag))
    hist = np.bincount(ph, weights=onset, minlength=nb)[:nb]
    hist = hist + 0.5 * (np.roll(hist, 1) + np.roll(hist, -1))
    return int(np.argmax(hist))


def _grid_values(sig: np.ndarray, positions: np.ndarray) -> np.ndarray:
    n = sig.size
    out = []
    for p in positions:
        i = int(round(p))
        if 1 <= i < n - 1:
            out.append(float(sig[i - 1:i + 2].max()))
    return np.asarray(out)


def _backbeat_parity(onset: np.ndarray, kick: np.ndarray, snare: np.ndarray, lag: float) -> float:
    """Cuánto parece `lag` el beat de un 4/4 con bombo en 1-3 y caja en 2-4: sobre la grilla de
    beats (fase por pulso), el bombo prefiere una paridad y la caja la otra. En el candidato
    al doble (beats/contratiempos) los dos prefieren la misma paridad; en el de la mitad
    (1 y 3) ninguno prefiere nada. Devuelve el producto de las preferencias opuestas, >= 0."""
    phi = _best_phase(onset, lag)
    count = int((onset.size - phi) / lag)
    if count < 4:
        return 0.0
    pos = phi + lag * np.arange(count)
    k = _grid_values(kick, pos)
    s = _grid_values(snare, pos)
    if k.size < 4 or s.size < 4:
        return 0.0
    ke, ko = k[0::2].mean(), k[1::2].mean()
    se, so = s[0::2].mean(), s[1::2].mean()
    dk = (ke - ko) / (ke + ko + 1e-9)
    ds = (se - so) / (se + so + 1e-9)
    return float(max(0.0, -dk * ds))


# Calibración de la confianza (regresión logística raw_conf -> P(octava correcta), ajustada
# con `tools/bpm_calibrate.py` sobre los 247 temas del 19-sep). Con esto 0.6 quiere decir
# "acierta 6 de 10 veces", no un número interno. Re-ajustar si cambia el puntaje.
_CONF_LOGIT_A = -1.18
_CONF_LOGIT_B = 8.26


def _calibrated_confidence(raw: float) -> float:
    return float(1.0 / (1.0 + np.exp(-(_CONF_LOGIT_A + _CONF_LOGIT_B * raw))))


def _no_pulse() -> BpmResult:
    """Centinela "sin pulso": value 0, sin alternativas. No es un BPM: `has_pulse()` lo
    distingue y `analyze_fragment` lo saca del resultado."""
    return BpmResult(value=0.0, confidence=0.05, alternatives=[], ambiguous=False, method=BPM_METHOD)


def has_pulse(bpm: BpmResult | None) -> bool:
    """True si el resultado trae un tempo real (contrato C2: con `value` hay alternativas)."""
    return bpm is not None and bpm.value > 0 and bool(bpm.alternatives)


def bpm_from_onset(
    onset: np.ndarray,
    sr: int = SR,
    *,
    kick_onset: np.ndarray | None = None,
    snare_onset: np.ndarray | None = None,
    params: BpmParams = DEFAULT_PARAMS,
) -> BpmResult:
    """
    Decide el tempo a partir de la envolvente de onset (hop 512) por evidencia:

    1. Candidatos: los `_MAX_PEAKS` picos más altos de la autocorrelación entre 40 y 240 BPM,
       más x0.5 y x2 de cada uno (dentro del rango). Cada candidato se ajusta al pico real
       más cercano con interpolación parabólica (nada de 117.5/123/129.2 cuantizados).
    2. Puntaje por candidato = jerarquía métrica (ver `BpmParams`) + backbeat opcional.
    3. `value` = el de mayor puntaje. `alternatives` = todos, ordenados, con `support` = el
       puntaje (0..1). `ambiguous` = el segundo está a menos de `ambiguous_ratio` del primero.

    Sin prior de gusto: si el cliente prefiere 76 a 152, lo elige él entre las alternativas.

    Sin pulso (envolvente vacía, plana o silencio) devuelve el centinela `NO_PULSE`
    (`value=0.0`, sin alternativas): el harness lo cuenta como error y `analyze_fragment`
    lo convierte en `bpm=None`. Nunca sale como dato hacia el cliente.
    """
    onset = np.asarray(onset, dtype=np.float64)
    if onset.size < 8 or not np.isfinite(onset).all() or onset.max() <= 0:
        return _no_pulse()
    ac = _autocorr(onset, sr, params.detrend)
    if ac.size <= 3 or ac[0] <= 0:
        return _no_pulse()
    norm = float(ac[0]) + 1e-9

    def S(lag: float) -> float:
        return float(np.clip(_peak_near(ac, lag)[1] / norm, 0.0, 1.0)) if lag >= 1.0 else 0.0

    use_backbeat = params.backbeat_weight > 0 and kick_onset is not None and snare_onset is not None
    kick = np.asarray(kick_onset, dtype=np.float64) if use_backbeat else None
    snare = np.asarray(snare_onset, dtype=np.float64) if use_backbeat else None

    lag_lo, lag_hi = _lag_of(_CAND_MAX, sr), _lag_of(_CAND_MIN, sr)
    peaks = _local_maxima(ac, lag_lo, lag_hi)
    peaks.sort(key=lambda i: ac[i], reverse=True)
    seeds: list[float] = [float(i) for i in peaks[:_MAX_PEAKS]]
    if not seeds:
        # Sin picos (envolvente plana): respaldo con el estimador de librosa, plegado.
        tempo = librosa.feature.tempo(onset_envelope=onset.astype(np.float32), sr=sr, hop_length=_HOP)
        folded = _fold(float(np.atleast_1d(tempo)[0]))
        if folded <= 0:
            return _no_pulse()
        seeds = [_lag_of(folded, sr)]

    # x0.5 / x2 de cada semilla (en lags: x2 / x0.5), dentro del rango físico.
    lags: list[float] = []
    for l in seeds:
        for f in (1.0, 2.0, 0.5):
            cand = l * f
            if lag_lo <= cand <= lag_hi:
                lags.append(cand)
    if not lags:
        return _no_pulse()

    # Evaluar: cada lag se ajusta al pico real más cercano y se puntúa por jerarquía.
    evaluated: list[tuple[float, float, float]] = []  # (bpm, S(l), score)
    for l in lags:
        l_ref, v = _peak_near(ac, l)
        s1 = float(np.clip(v / norm, 0.0, 1.0))
        score = (
            s1
            + params.sub_weight * S(l_ref / 2.0)
            - params.subsub_weight * S(l_ref / 4.0)
            + params.sup_weight * S(l_ref * 2.0)
        )
        if use_backbeat and kick is not None and snare is not None:
            score += params.backbeat_weight * _backbeat_parity(onset, kick, snare, l_ref)
        evaluated.append((_bpm_of(l_ref, sr), s1, score))

    # Dedupe a +-3%: se queda el de mayor puntaje.
    evaluated.sort(key=lambda t: t[2], reverse=True)
    kept: list[tuple[float, float, float]] = []
    for bpm, s1, score in evaluated:
        if any(abs(bpm - k[0]) / k[0] <= _DEDUPE_TOL for k in kept):
            continue
        kept.append((bpm, s1, score))

    best_bpm, best_s1, best_score = kept[0]
    second_score = kept[1][2] if len(kept) > 1 else 0.0
    ambiguous = bool(len(kept) > 1 and second_score >= params.ambiguous_ratio * best_score)

    # Confianza: fuerza del pico x margen del puntaje sobre el segundo (baja cuando dos
    # octavas compiten, que es justo cuando nos equivocamos), pasada por una calibración
    # logística ajustada con el dataset para que se lea como probabilidad de acierto.
    margen = (best_score - second_score) / (best_score + 1e-9) if best_score > 0 else 0.0
    raw_conf = float(np.clip(best_s1, 0.0, 1.0)) * (0.55 + 0.45 * float(np.clip(margen, 0.0, 1.0)))
    conf = _calibrated_confidence(raw_conf)
    # `support` = puntaje en 0..1: lo que decidió, para que el cliente compare candidatos.
    scale = max(best_score, 1e-9)
    return BpmResult(
        value=round(best_bpm, 1),
        confidence=round(float(np.clip(conf, 0.05, 0.98)), 2),
        alternatives=[
            BpmAlternative(value=round(b, 1), support=round(float(np.clip(sc / scale, 0.0, 1.0)), 3))
            for b, _, sc in kept
        ],
        ambiguous=ambiguous,
        method=BPM_METHOD,
    )


def _estimate_bpm(y: np.ndarray, sr: int, params: BpmParams = DEFAULT_PARAMS) -> BpmResult:
    """BPM desde audio: mel una sola vez -> envolvente completa (+ bombo y caja si el
    backbeat está prendido) -> `bpm_from_onset`."""
    S = _logmel(y, sr)
    onset = onset_from_logmel(S, sr)
    kick = snare = None
    if params.backbeat_weight > 0:
        kick = onset_from_logmel(S, sr, BAND_KICK)
        snare = onset_from_logmel(S, sr, BAND_SNARE)
    return bpm_from_onset(onset, sr, kick_onset=kick, snare_onset=snare, params=params)


# =============================================================================== key


def _estimate_key(y: np.ndarray, sr: int) -> KeyResult | None:
    """Tonalidad por correlación del perfil de chroma con Krumhansl-Kessler. `None` cuando
    no hay perfil (silencio, recorte vacío: chroma todo cero o constante, donde la
    correlación es NaN): antes salía "C major" con confianza 0.0, un valor inventado."""
    if y.size < sr:  # menos de 1 s: no hay perfil que valga
        return None
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    profile = chroma.mean(axis=1)
    if not np.isfinite(profile).all() or profile.sum() <= 0 or float(profile.std()) <= 1e-9:
        return None
    profile = profile / profile.sum()

    best_corr = -2.0
    best_idx = 0
    best_is_major = True
    for i in range(12):
        rotated = np.roll(profile, -i)
        for is_major, ks in ((True, KS_MAJOR), (False, KS_MINOR)):
            corr = float(np.corrcoef(rotated, ks)[0, 1])
            if np.isfinite(corr) and corr > best_corr:
                best_corr, best_idx, best_is_major = corr, i, is_major
    if best_corr < -1.0:  # ninguna correlación válida: sin tonalidad
        return None

    mode = "major" if best_is_major else "minor"
    confidence = round(float(np.clip((best_corr + 1) / 2, 0.0, 1.0)), 2)
    return KeyResult(value=f"{PITCH_CLASSES[best_idx]} {mode}", confidence=confidence)


# =============================================================================== análisis


def load_fragment(frag: Fragment) -> tuple[np.ndarray, int]:
    """Carga el WAV del recorte (ya viene mono 22050: sr=None evita el resample)."""
    y, sr = librosa.load(frag.path, sr=None, mono=True)
    return y, int(sr)


# Menos que esto de audio real no es una ventana de análisis: es un recorte que quedó
# fuera del track (start_sec más allá del final con `duration` desconocida) o casi.
_MIN_FRAGMENT_SEC = 2.0


def analyze_fragment(frag: Fragment, params: BpmParams = DEFAULT_PARAMS) -> AnalyzeResult:
    """BPM + tonalidad sobre un recorte ya hecho. La ventana queda en el resultado.

    Sin pulso medible (silencio, fade) el resultado va con `bpm=None`; sin perfil tonal,
    `key=None`. Un recorte (casi) vacío es un error (-> 502 con detalle), no un análisis:
    pasa cuando `start_sec` cae fuera del track y la fuente no informó la duración."""
    y, sr = load_fragment(frag)
    if y.size < sr * _MIN_FRAGMENT_SEC:
        raise RuntimeError(
            f"recorte vacío ({y.size / sr:.1f}s de audio desde {frag.start:.0f}s): la ventana "
            "quedó fuera del track; probá con otro start_sec"
        )
    bpm: BpmResult | None = _estimate_bpm(y, sr, params)
    if has_pulse(bpm):
        assert bpm is not None
        bpm.window = BpmWindow(start_sec=round(frag.start, 2), seconds=frag.seconds)
    else:
        log.info("sin pulso medible en %s (desde %.0fs): bpm=None", frag.path, frag.start)
        bpm = None
    return AnalyzeResult(bpm=bpm, key=_estimate_key(y, sr), duration_sec=frag.source_duration)
    # TODO(F2): mood/instrumentos con Essentia (modelos MusiCNN) -> AnalyzeResult.mood/instruments
