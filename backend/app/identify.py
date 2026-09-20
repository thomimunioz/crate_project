"""Endpoint de identificación por huella acústica (Capa 2, opt-in). Sync -> threadpool."""
from fastapi import APIRouter, HTTPException

from .analyze import http_error
from .config import settings
from .dsp import download_audio
from .fingerprint import FingerprintUnavailable, ensure_available, identify_fragment
from .models import IdentifyRequest, IdentifyResult

router = APIRouter()


@router.post("/identify", response_model=IdentifyResult)
def identify(req: IdentifyRequest) -> IdentifyResult:
    seconds = req.seconds or settings.identify_seconds
    try:
        ensure_available()
    except FingerprintUnavailable as exc:
        # No está configurado: degradar con un mensaje accionable, no con un 500.
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        # Misma descarga temporal que /analyze; el recorte arranca en 0 (o donde pida el
        # cliente): es donde alinea la huella de referencia de AcoustID.
        with download_audio(req.url) as audio:
            return identify_fragment(audio.cut(float(req.start_sec or 0), seconds))
    except FingerprintUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - se clasifica por texto, ver ytdl.error_kind
        raise http_error(exc, "identificación") from exc
