"""CRATE backend - FastAPI. Proxy (CORS/scraping) + análisis de audio (opt-in)."""
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from . import ytdl
from .config import settings
from .proxy import router as proxy_router
from .analyze import router as analyze_router
from .identify import router as identify_router
from .discover import router as discover_router

app = FastAPI(title="CRATE backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(proxy_router)
app.include_router(analyze_router)
app.include_router(identify_router)
app.include_router(discover_router)


@app.get("/health")
def health(refresh: bool = Query(False)) -> dict[str, Any]:
    """`ok` = se puede bajar y recortar audio: toolchain completo (yt-dlp + yt-dlp-ejs +
    runtime JS + ffmpeg) Y YouTube no tiene marcada esta IP (bot-check reciente).
    `tools` dice qué hay, qué falta y cómo arreglarlo; `youtube.blocked_at` dice desde
    cuándo está marcada la IP (o null). Mientras dure el cooldown el motivo va también en
    `tools.problems`, que es lo que la UI muestra. `?refresh=1` vuelve a mirar el sistema
    (después de instalar node/ffmpeg con el backend levantado); el bloqueo no se refresca
    a mano: lo levanta una descarga que ande, o el cooldown."""
    if refresh:
        ytdl.refresh()
    tools = ytdl.toolchain()
    block = ytdl.youtube_block()
    if block is not None:
        tools["problems"] = [*tools["problems"], f"{ytdl.blocked_detail()} (visto {block['blocked_at']})"]
    return {
        "ok": bool(tools["ok"]) and block is None,
        "tools": tools,
        "youtube": {
            "blocked": block is not None,
            "blocked_at": block["blocked_at"] if block else None,
            "detail": block["detail"] if block else None,
        },
    }
