"""Proxy con allowlist. Resuelve CORS y scraping SIN ser un open relay."""
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from .config import settings

router = APIRouter()


def _host_allowed(host: str) -> bool:
    host = host.lower()
    return any(host == h or host.endswith("." + h) for h in settings.allowlist)


@router.get("/proxy")
async def proxy(url: str = Query(..., description="URL absoluta a relayear")) -> JSONResponse:
    host = urlparse(url).hostname or ""
    if not _host_allowed(host):
        raise HTTPException(status_code=403, detail=f"host no permitido: {host!r}")

    headers = {
        "User-Agent": settings.app_user_agent,
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"proxy error: {exc}") from exc

    content_type = r.headers.get("content-type", "")
    if "json" in content_type:
        return JSONResponse(status_code=r.status_code, content=r.json())
    # fallback: devolver texto crudo (ej. para scraping HTML en F2)
    return JSONResponse(status_code=r.status_code, content={"raw": r.text})
