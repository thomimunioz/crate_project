"""Endpoint de análisis de audio (Capa 2, opt-in). Sync -> FastAPI lo corre en threadpool."""
import httpx
from fastapi import APIRouter, HTTPException

from . import ytdl
from .config import settings
from .dsp import analyze_fragment, download_audio, smart_start
from .fingerprint import FingerprintUnavailable, ensure_available, identify_fragment
from .models import AnalyzeRequest, AnalyzeResult

router = APIRouter()


def http_error(exc: BaseException, que: str) -> HTTPException:
    """Mapea un error del path de descarga/DSP al status que le corresponde (contrato C2):
    referencia inválida -> 400; falta toolchain -> 503 con qué instalar; bot-check de
    YouTube -> 503 con qué hacer (el video existe, la IP está marcada); video no
    disponible -> 404; el resto -> 502. El `detail` va siempre legible: es lo que el
    AnalyzePanel le muestra al usuario."""
    kind = ytdl.error_kind(exc)
    text = ytdl.error_text(exc)
    if kind == "invalid":
        return HTTPException(status_code=400, detail=text)
    if kind == "toolchain":
        return HTTPException(status_code=503, detail=text)
    if kind == "blocked":
        return HTTPException(status_code=503, detail=ytdl.blocked_detail(exc))
    if kind == "unavailable":
        return HTTPException(status_code=404, detail=f"video no disponible: {text}")
    return HTTPException(status_code=502, detail=f"{que} falló: {text}")


def analyze_one(req: AnalyzeRequest) -> AnalyzeResult:
    """Una descarga temporal, uno o dos recortes: BPM/key sobre la ventana (`start_sec` o
    `smart_start`), huella desde el segundo 0 si se pidió `identify`. Todo se borra al salir.

    Solo la descarga y el DSP principal pueden fallar el request. Si la huella falla
    (fpcalc, AcoustID caído, key rechazada), el BPM/key ya calculados se devuelven igual
    y el motivo va en `identification_error`."""
    seconds = req.seconds or settings.analyze_seconds
    identify = req.identify
    unavailable: str | None = None
    if identify:
        try:
            ensure_available()
        except FingerprintUnavailable as exc:
            # El análisis igual sirve: sigue sin identificar, avisando por qué.
            identify, unavailable = False, str(exc)

    with download_audio(req.url) as audio:
        start = smart_start(audio.duration) if req.start_sec is None else float(req.start_sec)
        result = analyze_fragment(audio.cut(start, seconds))
        if identify:
            try:
                result.identification = identify_fragment(audio.cut(0.0, settings.identify_seconds))
            except (FingerprintUnavailable, RuntimeError, httpx.HTTPError) as exc:
                unavailable = str(exc)
        result.identification_error = unavailable
        return result


@router.post("/analyze", response_model=AnalyzeResult)
def analyze(req: AnalyzeRequest) -> AnalyzeResult:
    # TODO(F1): lote opt-in con progreso (job en memoria + polling) cuando se analicen N guardados.
    try:
        return analyze_one(req)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - se clasifica por texto, ver ytdl.error_kind
        raise http_error(exc, "análisis") from exc
