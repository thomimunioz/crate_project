"""Endpoint de análisis de audio (Capa 2, opt-in). Sync → FastAPI lo corre en threadpool."""
from fastapi import APIRouter, HTTPException

from .models import AnalyzeRequest, AnalyzeResult
from .dsp import analyze_url

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResult)
def analyze(req: AnalyzeRequest) -> AnalyzeResult:
    # TODO(F1): si tarda mucho, mover a un job async con progreso (WebSocket/polling).
    try:
        return analyze_url(req.url, seconds=req.seconds, start=req.start_sec)
    except Exception as exc:  # noqa: BLE001 — degradar con un error claro para el front
        raise HTTPException(status_code=502, detail=f"análisis falló: {exc}") from exc
