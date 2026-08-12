"""
Descubrimiento sin quota.

`search.list` de la API de YouTube cuesta **100 unidades** de las 10.000 diarias:
son ~100 búsquedas por día para toda la app. yt-dlp habla el mismo InnerTube que
usa el reproductor web, sin key y sin quota.

La división del trabajo es a propósito: yt-dlp BUSCA (gratis) y la API oficial
trae la metadata de esos ids con `videos.list`, que cuesta 1 unidad cada 50.
Una búsqueda pasa de 100 unidades a 1.

Devuelve solo ids y lo básico: la descripción y los tags —que es de donde salen
las pistas duras— los trae el frontend con `videos.list`, que ya sabe hacerlo.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query
from yt_dlp import YoutubeDL

from .models import DiscoverItem, DiscoverResult

router = APIRouter()

_MAX = 50

# extract_flat evita abrir la página de cada video: la búsqueda tarda ~2s en vez
# de un minuto. La metadata completa la pide después el frontend por videos.list.
_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "extract_flat": True,
    "noplaylist": False,
}


def _buscar(query: str, limit: int) -> list[DiscoverItem]:
    with YoutubeDL(_OPTS) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)

    items: list[DiscoverItem] = []
    for e in (info or {}).get("entries") or []:
        vid = e.get("id")
        if not vid:
            continue
        items.append(
            DiscoverItem(
                video_id=vid,
                title=e.get("title") or "",
                uploader=e.get("uploader") or e.get("channel"),
                channel_id=e.get("channel_id"),
                duration_sec=int(e["duration"]) if e.get("duration") else None,
                views=int(e["view_count"]) if e.get("view_count") else None,
            )
        )
    return items


@router.get("/discover")
async def discover(
    q: str = Query(..., min_length=1, description="qué buscar en YouTube"),
    limit: int = Query(20, ge=1, le=_MAX),
) -> DiscoverResult:
    """Busca en YouTube sin gastar quota. Bloqueante → va al threadpool."""
    try:
        items = await asyncio.to_thread(_buscar, q, limit)
    except Exception as exc:  # noqa: BLE001 — degradar con un error claro para el front
        raise HTTPException(status_code=502, detail=f"búsqueda con yt-dlp falló: {exc}") from exc
    return DiscoverResult(query=q, items=items)
