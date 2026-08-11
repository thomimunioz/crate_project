"""
DSP: baja un fragmento con yt-dlp y estima BPM + tonalidad con Librosa.
Siempre con confidence. Nunca redistribuye audio: el fragmento temporal se borra.
El fragmento se baja UNA vez y lo comparten los dos usos (BPM/key y huella acústica).
Ver .claude/agents/dsp-analyst.md
"""
from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import librosa
import numpy as np
from yt_dlp import YoutubeDL
from yt_dlp.utils import download_range_func

from .config import settings
from .models import AnalyzeResult, BpmResult, KeyResult

PITCH_CLASSES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Perfiles Krumhansl-Kessler para estimación de tonalidad
KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


@dataclass(frozen=True)
class Fragment:
    """Un fragmento temporal en disco + lo que sabemos del track del que salió."""
    path: str
    start: int
    seconds: int
    source_duration: float | None  # duración del track completo, según la fuente


def _downloaded_path(info: dict, ydl: YoutubeDL) -> str:
    """yt-dlp remuxea al recortar, así que el nombre real puede no ser el previsto."""
    for entry in info.get("requested_downloads") or []:
        path = entry.get("filepath")
        if path and os.path.exists(path):
            return path
    return ydl.prepare_filename(info)


@contextmanager
def fragment(url: str, start: int, seconds: int) -> Iterator[Fragment]:
    """
    Baja un fragmento (nunca el track entero) y garantiza el borrado, falle lo que falle.
    Una sola descarga, varios usos: Librosa y fpcalc leen el mismo archivo.
    """
    os.makedirs(settings.tmp_dir, exist_ok=True)
    out_tmpl = os.path.join(settings.tmp_dir, f"{uuid.uuid4().hex}.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_tmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        # recorta el fragmento en la descarga (requiere ffmpeg)
        "download_ranges": download_range_func(None, [(start, start + seconds)]),
        "force_keyframes_at_cuts": True,
    }
    path: str | None = None
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = _downloaded_path(info, ydl)
            duration = info.get("duration")
        yield Fragment(
            path=path,
            start=start,
            seconds=seconds,
            source_duration=float(duration) if duration else None,
        )
    finally:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


_HOP = 512
# Rango musical útil: boombap, soul y jazz viven acá. Fuera de esto es octava mal leída.
_BPM_MIN, _BPM_MAX = 60.0, 180.0


def _fold(bpm: float) -> float:
    """Lleva el tempo al rango musical duplicando o partiendo por dos."""
    while bpm < _BPM_MIN:
        bpm *= 2
    while bpm > _BPM_MAX:
        bpm /= 2
    return bpm


def _support(ac: np.ndarray, sr: int, bpm: float) -> float:
    """Cuánta evidencia hay en la autocorrelación del onset para ese BPM."""
    lag = int(round(60.0 * sr / (_HOP * bpm)))
    if lag <= 0 or lag >= ac.size:
        return 0.0
    lo, hi = max(1, lag - 1), min(ac.size, lag + 2)
    return float(ac[lo:hi].max() / (ac[0] + 1e-9))


def _estimate_bpm(y: np.ndarray, sr: int) -> BpmResult:
    """
    BPM con la octava resuelta.

    `beat_track` se equivoca de octava seguido (devuelve el doble o la mitad) y
    la estabilidad del tempograma NO lo delata: un tempo duplicado es igual de
    estable, así que salía un 198 BPM con confianza 0.85 en un tema de 99. Acá se
    elige entre las tres octavas por la evidencia real en la autocorrelación del
    onset, y la confianza baja cuando dos octavas compiten — que es justo cuando
    nos equivocamos.
    """
    onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=_HOP)
    ac = librosa.autocorrelate(onset)
    if ac.size <= 1:
        return BpmResult(value=0.0, confidence=0.05)

    tempo, _ = librosa.beat.beat_track(y=y, sr=sr, hop_length=_HOP)
    base = _fold(float(np.atleast_1d(tempo)[0]))

    candidatos = sorted({round(_fold(base * f), 3) for f in (0.5, 1.0, 2.0)})
    puntajes = sorted(
        ((bpm, _support(ac, sr, bpm)) for bpm in candidatos),
        key=lambda par: par[1],
        reverse=True,
    )
    mejor, fuerza = puntajes[0]
    segundo = puntajes[1][1] if len(puntajes) > 1 else 0.0

    margen = (fuerza - segundo) / (fuerza + 1e-9) if fuerza > 0 else 0.0
    conf = float(np.clip(fuerza, 0.0, 1.0)) * (0.55 + 0.45 * float(np.clip(margen, 0.0, 1.0)))
    return BpmResult(value=round(mejor, 1), confidence=round(float(np.clip(conf, 0.05, 0.98)), 2))


def _estimate_key(y: np.ndarray, sr: int) -> KeyResult:
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    profile = chroma.mean(axis=1)
    if profile.sum() > 0:
        profile = profile / profile.sum()

    best_corr = -2.0
    best_idx = 0
    best_is_major = True
    for i in range(12):
        rotated = np.roll(profile, -i)
        for is_major, ks in ((True, KS_MAJOR), (False, KS_MINOR)):
            corr = float(np.corrcoef(rotated, ks)[0, 1])
            if corr > best_corr:
                best_corr, best_idx, best_is_major = corr, i, is_major

    mode = "major" if best_is_major else "minor"
    confidence = round(float(np.clip((best_corr + 1) / 2, 0.0, 1.0)), 2)
    return KeyResult(value=f"{PITCH_CLASSES[best_idx]} {mode}", confidence=confidence)


def analyze_fragment(frag: Fragment, seconds: int | None = None) -> AnalyzeResult:
    """BPM + tonalidad sobre un fragmento ya bajado. `seconds` limita cuánto se decodifica."""
    y, sr = librosa.load(
        frag.path, sr=22050, mono=True, duration=float(seconds or frag.seconds)
    )
    return AnalyzeResult(bpm=_estimate_bpm(y, sr), key=_estimate_key(y, sr))
    # TODO(F2): mood/instrumentos con Essentia (modelos MusiCNN) → AnalyzeResult.mood/instruments
