"""Endpoint de análisis de audio (Capa 2, opt-in). Sync → FastAPI lo corre en threadpool."""
from fastapi import APIRouter, HTTPException

from .config import settings
from .dsp import analyze_fragment, fragment
from .fingerprint import FingerprintUnavailable, ensure_available, identify_fragment
from .models import AnalyzeRequest, AnalyzeResult

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResult)
def analyze(req: AnalyzeRequest) -> AnalyzeResult:
    # TODO(F1): si tarda mucho, mover a un job async con progreso (WebSocket/polling).
    seconds = req.seconds or settings.analyze_seconds
    identify = req.identify
    unavailable: str | None = None
    if identify:
        try:
            ensure_available()
        except FingerprintUnavailable as exc:
            # El análisis igual sirve: sigue sin identificar, avisando por qué.
            identify, unavailable = False, str(exc)

    # Con identificación se baja UN fragmento más largo y lo usan los dos:
    # BPM/key leen los primeros `seconds`, la huella usa todo.
    download_seconds = max(seconds, settings.identify_seconds) if identify else seconds
    try:
        with fragment(req.url, req.start_sec or 0, download_seconds) as frag:
            result = analyze_fragment(frag, seconds)
            if identify:
                result.identification = identify_fragment(frag)
            result.identification_error = unavailable
            return result
    except Exception as exc:  # noqa: BLE001 — degradar con un error claro para el front
        raise HTTPException(status_code=502, detail=f"análisis falló: {exc}") from exc
