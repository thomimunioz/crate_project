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


def _auth_for(host: str) -> dict[str, str]:
    """Credenciales por host. El browser nunca las ve."""
    if host.lower().endswith("discogs.com") and settings.discogs_key and settings.discogs_secret:
        return {
            "Authorization": (
                f"Discogs key={settings.discogs_key}, secret={settings.discogs_secret}"
            )
        }
    return {}


@router.get("/proxy")
async def proxy(url: str = Query(..., description="URL absoluta a relayear")) -> JSONResponse:
    host = urlparse(url).hostname or ""
    if not _host_allowed(host):
        raise HTTPException(status_code=403, detail=f"host no permitido: {host!r}")

    headers = {
        "User-Agent": settings.app_user_agent,
        "Accept": "application/json",
        **_auth_for(host),
    }
    # Seguir redirects a ciegas saltea la allowlist: un host permitido puede
    # responder 302 hacia 127.0.0.1 o hacia una IP interna y el proxy lo trae
    # igual. Por eso se siguen a mano, revalidando el host en CADA salto.
    # (Auditoria del 27-oct-2026.)
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
            for _ in range(5):
                r = await client.get(url, headers=headers)
                if r.status_code not in (301, 302, 303, 307, 308):
                    break
                destino = str(r.headers.get("location") or "")
                if not destino:
                    break
                url = str(httpx.URL(url).join(destino))
                salto = urlparse(url).hostname or ""
                if not _host_allowed(salto):
                    raise HTTPException(
                        status_code=403,
                        detail=f"redirect a host no permitido: {salto!r}")
                headers = {**headers, **_auth_for(salto)}
            else:
                raise HTTPException(status_code=502, detail="demasiados redirects")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"proxy error: {exc}") from exc

    content_type = r.headers.get("content-type", "")
    if "json" in content_type:
        return JSONResponse(status_code=r.status_code, content=r.json())
    # fallback: devolver texto crudo (ej. para scraping HTML en F2)
    return JSONResponse(status_code=r.status_code, content={"raw": r.text})
