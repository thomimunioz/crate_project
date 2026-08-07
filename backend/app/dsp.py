"""
DSP: baja un fragmento con yt-dlp y estima BPM + tonalidad con Librosa.
Siempre con confidence. Nunca redistribuye audio: el fragmento temporal se borra.
Ver .claude/agents/dsp-analyst.md
"""
from __future__ import annotations

import os
import uuid

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


def _download_fragment(url: str, start: int, seconds: int) -> str:
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
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


def _estimate_bpm(y: np.ndarray, sr: int) -> BpmResult:
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    value = float(np.atleast_1d(tempo)[0])
    # confianza heurística: qué tan estable es el tempograma
    onset = librosa.onset.onset_strength(y=y, sr=sr)
    ac = librosa.autocorrelate(onset)
    conf = float(np.clip((ac[1:].max() / (ac[0] + 1e-9)), 0.0, 1.0)) if ac.size > 1 else 0.6
    return BpmResult(value=round(value, 1), confidence=round(0.5 + 0.5 * conf, 2))


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


def analyze_url(url: str, seconds: int | None = None, start: int | None = None) -> AnalyzeResult:
    seconds = seconds or settings.analyze_seconds
    start = start or 0
    path: str | None = None
    try:
        path = _download_fragment(url, start, seconds)
        y, sr = librosa.load(path, sr=22050, mono=True, duration=float(seconds))
        return AnalyzeResult(bpm=_estimate_bpm(y, sr), key=_estimate_key(y, sr))
        # TODO(F2): mood/instrumentos con Essentia (modelos MusiCNN) → AnalyzeResult.mood/instruments
    finally:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
