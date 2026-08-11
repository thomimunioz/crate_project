"""Endpoint de identificación por huella acústica (Capa 2, opt-in). Sync → threadpool."""
from fastapi import APIRouter, HTTPException

from .config import settings
from .dsp import fragment
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
        # Desde el arranque del track: es donde alinea la huella de referencia.
        with fragment(req.url, req.start_sec or 0, seconds) as frag:
            return identify_fragment(frag)
    except FingerprintUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — degradar con un error claro para el front
        raise HTTPException(status_code=502, detail=f"identificación falló: {exc}") from exc
