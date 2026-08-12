"""
Identificación por huella acústica (Chromaprint + AcoustID).

Por qué existe: el cruce por texto contra catálogo se clava en 57% y falla siempre en
lo mismo — títulos en kanji (city pop) y títulos sueltos sin artista ("Ennui").
La huella no depende del texto, así que puede resolver justo esos casos.

Devuelve candidatos con confidence, nunca una identificación "segura":
la huella es evidencia fuerte, pero se calcula sobre un fragmento, no sobre el track entero.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time

import httpx

from .config import settings
from .dsp import Fragment
from .models import IdentifyCandidate, IdentifyResult

ACOUSTID_LOOKUP_URL = "https://api.acoustid.org/v2/lookup"
# AcoustID permite 3 req/seg por API key.
_MIN_INTERVAL_SEC = 1 / 3
_MAX_CANDIDATES = 5
# Largo de referencia de chromaprint: con menos audio la huella es evidencia más flaca.
_FULL_FINGERPRINT_SEC = 120

_throttle_lock = threading.Lock()
_last_lookup = 0.0


class FingerprintUnavailable(RuntimeError):
    """Falta una pieza de configuración (fpcalc o la API key). No es un fallo del análisis."""


def _throttle() -> None:
    """Serializa los lookups para no pasarnos de 3 req/seg."""
    global _last_lookup
    with _throttle_lock:
        wait = _MIN_INTERVAL_SEC - (time.monotonic() - _last_lookup)
        if wait > 0:
            time.sleep(wait)
        _last_lookup = time.monotonic()


def fpcalc_path() -> str:
    """Ruta a fpcalc: primero la configurada (CRATE_FPCALC_PATH), después el PATH."""
    configured = settings.fpcalc_path.strip()
    if configured:
        if not os.path.isfile(configured):
            raise FingerprintUnavailable(
                f"CRATE_FPCALC_PATH apunta a {configured!r} y ahí no hay nada. "
                "Corregí la ruta o dejala vacía para usar el PATH."
            )
        return configured

    found = shutil.which("fpcalc")
    if found:
        return found

    raise FingerprintUnavailable(
        "Falta fpcalc (Chromaprint). Bajalo de "
        "https://github.com/acoustid/chromaprint/releases y poné la ruta al .exe en "
        "CRATE_FPCALC_PATH, o dejalo accesible desde el PATH."
    )


def compute_fingerprint(frag: Fragment) -> tuple[str, float]:
    """Corre fpcalc sobre el fragmento ya bajado → (huella comprimida, segundos huellados)."""
    cmd = [fpcalc_path(), "-json", "-length", str(frag.seconds), frag.path]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("fpcalc tardó demasiado") from exc

    if proc.returncode != 0:
        raise RuntimeError(f"fpcalc falló ({proc.returncode}): {proc.stderr.strip()[:300]}")

    try:
        data = json.loads(proc.stdout)
        return data["fingerprint"], float(data["duration"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"fpcalc devolvió algo raro: {proc.stdout.strip()[:200]}") from exc


def _confidence(score: float, fingerprint_seconds: float) -> float:
    """
    Confianza honesta: el score de AcoustID es similitud de huella sobre lo que le mandamos.
    Como huellamos un fragmento y no el track, descontamos por cobertura — con 45s nunca
    debería salir la misma confianza que con los 120s de referencia de chromaprint.
    """
    coverage = min(1.0, fingerprint_seconds / _FULL_FINGERPRINT_SEC)
    return round(score * (0.55 + 0.45 * coverage), 3)


def _to_candidates(results: list[dict], fingerprint_seconds: float) -> list[IdentifyCandidate]:
    """Aplana result → recordings. Un candidato por grabación, ordenados por score."""
    candidates: list[IdentifyCandidate] = []
    for result in results:
        acoustid = result.get("id") or ""
        score = float(result.get("score") or 0.0)
        confidence = _confidence(score, fingerprint_seconds)
        recordings = result.get("recordings") or []
        if not recordings:
            # Huella conocida pero sin metadata linkeada: se informa igual, sin inventar.
            candidates.append(
                IdentifyCandidate(acoustid=acoustid, score=score, confidence=confidence)
            )
            continue
        for rec in recordings:
            artists = rec.get("artists") or []
            duration = rec.get("duration")
            candidates.append(
                IdentifyCandidate(
                    acoustid=acoustid,
                    score=score,
                    confidence=confidence,
                    recording_mbid=rec.get("id"),
                    artist=", ".join(a.get("name", "") for a in artists) or None,
                    title=rec.get("title"),
                    releases=[
                        rg.get("title", "") for rg in (rec.get("releasegroups") or []) if rg.get("title")
                    ],
                    duration_sec=float(duration) if duration else None,
                )
            )

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:_MAX_CANDIDATES]


def _api_key() -> str:
    key = settings.acoustid_key.strip()
    if not key:
        raise FingerprintUnavailable(
            "Falta CRATE_ACOUSTID_KEY. Sacá una gratis en "
            "https://acoustid.org/new-application y ponela en el .env de la raíz."
        )
    return key


def ensure_available() -> None:
    """Chequeo de configuración ANTES de bajar audio: no vale bajar 2 min al pedo."""
    fpcalc_path()
    _api_key()


def lookup(fingerprint: str, duration_sec: int, fingerprint_seconds: float) -> list[IdentifyCandidate]:
    """Consulta AcoustID. POST porque la huella no entra cómoda en una query string."""
    key = _api_key()
    _throttle()
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.post(
                ACOUSTID_LOOKUP_URL,
                data={
                    "client": key,
                    "duration": str(duration_sec),
                    "fingerprint": fingerprint,
                    # OJO: AcoustID separa los valores de `meta` por ESPACIO.
                    # Con "+" o "," devuelve el match pero SIN metadata, y en
                    # form-encoded el "+" viaja como %2B, o sea literal.
                    "meta": "recordings releasegroups",
                },
                headers={"User-Agent": settings.app_user_agent},
            )
    except httpx.HTTPError as exc:
        raise RuntimeError(f"AcoustID no respondió: {exc}") from exc

    try:
        payload = r.json()
    except ValueError as exc:
        raise RuntimeError(f"AcoustID devolvió {r.status_code} sin JSON") from exc

    if payload.get("status") != "ok":
        message = (payload.get("error") or {}).get("message", "error desconocido")
        if "api key" in message.lower():
            raise FingerprintUnavailable(f"AcoustID rechazó la API key: {message}")
        raise RuntimeError(f"AcoustID: {message}")

    return _to_candidates(payload.get("results") or [], fingerprint_seconds)


def identify_fragment(frag: Fragment) -> IdentifyResult:
    """Fragmento ya bajado → candidatos de AcoustID. No baja nada por su cuenta."""
    fingerprint, fp_seconds = compute_fingerprint(frag)
    # AcoustID filtra candidatos por duración del track, así que le declaramos la del
    # track completo (la que reporta la fuente) y no la del fragmento; la huella igual
    # alinea porque arranca donde arranca el tema.
    duration_sec = int(round(frag.source_duration or fp_seconds))
    candidates = lookup(fingerprint, duration_sec, fp_seconds)
    return IdentifyResult(
        candidates=candidates,
        fingerprint_seconds=int(round(fp_seconds)),
        lookup_duration_sec=duration_sec,
    )
