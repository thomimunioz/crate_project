"""
Descubrimiento sin quota: buscar, y minar playlists y canales.

`search.list` de la API de YouTube cuesta **100 unidades** de las 10.000 diarias:
son ~100 búsquedas por día para toda la app. yt-dlp habla el mismo InnerTube que
usa el reproductor web, sin key y sin quota.

La división del trabajo es a propósito y vale para los tres endpoints: yt-dlp
BUSCA/LISTA (gratis, `extract_flat`: id, título, uploader, duración, views,
miniatura) y la API oficial trae la metadata rica de esos ids con `videos.list`
(descripción, tags, fecha; 1 unidad cada 50). Con playlists y canales el cliente
pide `videos.list` SOLO para la tanda que va a enriquecer, no para el pool entero:
una veta de 2.000 temas cuesta 40 unidades en total, y 0 hasta que se empieza a
enriquecer.

Lo que hay que saber de flat (medido el 20-sep-2026 con yt-dlp 2026.08.19):

- Playlist (`PL…`): ~1.6 s por 200 items. Las entries traen uploader/channel_id;
  `view_count` viene REDONDEADO (945000, 1700) → `views_approx=True`. El padre trae
  `playlist_count`. Ninguna entry trae description/upload_date/tags.
- Tab de canal (`/@handle/videos`): las entries vienen SIN uploader ni channel_id
  (están solo en el padre) y el padre no trae `playlist_count`. Por eso un canal se
  lista por su playlist de uploads (`UU` + id del canal sin el `UC`): las mismas
  entries pero con uploader/channel_id, y con el total (1.845 para "Music for empty
  rooms"). Si eso falla se cae al tab y se propaga uploader/channel_id del padre.
- `ytsearch`: `view_count` EXACTO y un recorte de la descripción; sin playlist.
- `playliststart`/`playlistend` (1-based) pagina de verdad: 101–150 de una playlist
  en 1.4 s; 1601–1800 de un canal de 1.845 en 7.5 s (pagina hasta llegar).
- Las entries flat NO traen `playlist_index` (yt-dlp devuelve el ie_result original,
  no la copia con los extras): se lee de `requested_entries` del padre.
- Borrados/privados: título `[Deleted video]`/`[Private video]` con duración y views
  en null. YouTube suele esconderlos ("1 unavailable video is hidden"); cuando
  aparecen se marcan `unavailable=True`, no se filtran.

Acá no hay filtro de basura ni ranking: eso es dominio y corre en el cliente; el
backend devuelve evidencia. Tampoco es un open relay: yt-dlp solo abre URLs que
arma este módulo sobre hosts de YouTube (`_ref_playlist` / `_ref_canal`).
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Callable
from typing import Any, TypeVar
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, HTTPException, Query
from yt_dlp import YoutubeDL

from . import ytdl
from .models import DiscoverItem, DiscoverListResult, DiscoverResult

log = logging.getLogger("crate.discover")

router = APIRouter()

T = TypeVar("T")

_SEARCH_MAX = 50
# Tope por tanda al minar. Un canal digger tiene miles de uploads: se pagina con
# `offset`, no se baja entero por accidente.
_LIST_MAX = 500
_LIST_DEFAULT = 200

# YouTube tira bot-check si se listan muchas playlists a la vez: de a dos como mucho.
_SEM = asyncio.Semaphore(2)

_YT_HOSTS = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"})

# Ids de playlist: PL (normales, 18 o 34 chars), UU (uploads de un canal), OL (álbum
# de YouTube Music), LL/FL (likes/favoritos, privadas pero válidas).
_PLAYLIST_ID_RE = re.compile(r"^(?:PL|UU|OL|LL|FL)[\w-]{10,}$")
_CHANNEL_ID_RE = re.compile(r"^UC[\w-]{22}$")
# Handles de YouTube: 3–30 chars, letras/números/_/-/. (con o sin arroba).
_HANDLE_RE = re.compile(r"^@?[\w.\-]{3,30}$")
_LEGACY_NAME_RE = re.compile(r"^[\w.\-]{1,100}$")

_UNAVAILABLE_TITLES = frozenset({"[deleted video]", "[private video]", "[unavailable video]"})


# --------------------------------------------------------------------------- refs


def _parse_yt_url(ref: str, que: str) -> Any:
    """Parsea una URL y exige host de YouTube. Sin esquema se asume https."""
    raw = ref if "://" in ref else f"https://{ref}"
    try:
        u = urlparse(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{que}: no entiendo {ref!r}") from exc
    host = (u.hostname or "").lower()
    if host not in _YT_HOSTS:
        raise HTTPException(
            status_code=400,
            detail=f"{que}: solo se aceptan URLs de YouTube (youtube.com / youtu.be), no {host or ref!r}",
        )
    return u


def _ref_playlist(ref: str) -> str:
    """Id de playlist (`PL…`, `UU…`) o URL de YouTube con `list=` → URL canónica de la
    playlist. Cualquier otra cosa es 400. Nunca deja pasar un host ajeno."""
    ref = ref.strip()
    if _PLAYLIST_ID_RE.match(ref):
        return f"https://www.youtube.com/playlist?list={ref}"
    u = _parse_yt_url(ref, "playlist")
    pid = (parse_qs(u.query).get("list") or [""])[0].strip()
    if pid and _PLAYLIST_ID_RE.match(pid):
        return f"https://www.youtube.com/playlist?list={pid}"
    raise HTTPException(
        status_code=400,
        detail="playlist: pasá un id (PL…) o una URL de YouTube con ?list=PL… (los mixes RD… no se listan)",
    )


def _ref_canal(ref: str) -> tuple[str | None, str]:
    """`UC…`, `@handle`, `handle`, o URL de canal (`/channel/UC…`, `/@handle`, `/c/x`,
    `/user/x`, con o sin `/videos`) → (channel_id si ya se sabe, URL canónica del canal).
    Cualquier otra cosa es 400."""
    ref = ref.strip()
    if _CHANNEL_ID_RE.match(ref):
        return ref, f"https://www.youtube.com/channel/{ref}"
    if _HANDLE_RE.match(ref):
        handle = ref if ref.startswith("@") else f"@{ref}"
        return None, f"https://www.youtube.com/{handle}"
    u = _parse_yt_url(ref, "canal")
    parts = [p for p in u.path.split("/") if p]
    if parts:
        if parts[0] == "channel" and len(parts) > 1 and _CHANNEL_ID_RE.match(parts[1]):
            return parts[1], f"https://www.youtube.com/channel/{parts[1]}"
        if parts[0].startswith("@") and _HANDLE_RE.match(parts[0]):
            return None, f"https://www.youtube.com/{parts[0]}"
        if parts[0] in ("c", "user") and len(parts) > 1 and _LEGACY_NAME_RE.match(parts[1]):
            return None, f"https://www.youtube.com/{parts[0]}/{parts[1]}"
    raise HTTPException(
        status_code=400,
        detail="canal: pasá un UC…, un @handle o una URL de canal de YouTube (/channel/UC…, /@handle, /c/…, /user/…)",
    )


# --------------------------------------------------------------------------- yt-dlp


def _opts(**extra: Any) -> dict[str, Any]:
    # extract_flat evita abrir la página de cada video: 200 items en ~2 s en vez
    # de minutos. Listar no necesita runtime JS; ydl_opts lo pone igual si lo hay.
    return ytdl.ydl_opts(noplaylist=False, extract_flat=True, skip_download=True, **extra)


class _NotFound(Exception):
    """Playlist/canal que no existe o es privado. yt-dlp lo envuelve como 'Unable to
    download API page: HTTP Error 404', que `ytdl.error_kind` lee como transitorio y
    reintentaría: acá se corta antes y va como 404. El mensaje no repite el texto de
    yt-dlp a propósito, para que no vuelva a clasificar como transitorio."""


_NOT_FOUND = (
    "does not exist",
    "requested entity was not found",
    "http error 404",
    "not found",
    "is private",
)


def _extract(url: str, *, process: bool = True, **extra: Any) -> dict[str, Any]:
    """`extract_info` con reintento corto (un 403/corte transitorio, 2 s). Con
    `process=False` devuelve solo el padre (id, título, channel_id) en ~0.5 s."""

    def go() -> dict[str, Any]:
        try:
            with YoutubeDL(_opts(**extra)) as ydl:
                return ydl.extract_info(url, download=False, process=process) or {}
        except Exception as exc:  # noqa: BLE001 — solo reclasifica los 404, el resto sigue
            text = str(exc).lower()
            if ytdl.error_kind(exc) not in ("toolchain", "blocked") and any(s in text for s in _NOT_FOUND):
                raise _NotFound(f"YouTube no encontró (o no deja ver) {url}") from exc
            raise

    t0 = time.perf_counter()
    info = ytdl.with_retry(go, tries=2, backoff=(2,))
    log.info("yt-dlp %s%s: %.1fs", url, "" if process else " (solo padre)", time.perf_counter() - t0)
    return info


def _thumbnail(e: dict[str, Any], video_id: str, unavailable: bool) -> str | None:
    if unavailable:
        return None
    best: dict[str, Any] | None = None
    for t in e.get("thumbnails") or []:
        if not t.get("url"):
            continue
        if best is None or (t.get("width") or 0) > (best.get("width") or 0):
            best = t
    if best:
        return str(best["url"])
    # Siempre existe para un video público; no es un dato inventado, es la URL fija de YouTube.
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else None


def _item_de(
    e: dict[str, Any],
    padre_canal: dict[str, Any] | None = None,
    *,
    views_approx: bool,
    index: int | None = None,
) -> DiscoverItem:
    """Una entry flat → DiscoverItem. `padre_canal` se pasa SOLO cuando el padre es un
    canal (tab de videos): ahí las entries vienen sin uploader/channel_id y son del
    canal por definición. En una playlist el dueño no es el uploader del video: no
    se propaga."""
    video_id = str(e.get("id") or "")
    title = str(e.get("title") or "")
    duration = e.get("duration")
    views = e.get("view_count")
    # 0 views es un dato; None es "no vino". Por eso `is not None` y no truthiness.
    duration_sec = int(duration) if duration is not None else None
    views_int = int(views) if views is not None else None
    unavailable = title.strip().lower() in _UNAVAILABLE_TITLES or (
        not title and duration_sec is None and views_int is None
    )

    padre = padre_canal or {}
    uploader = e.get("uploader") or e.get("channel") or padre.get("uploader") or padre.get("channel")
    channel_id = e.get("channel_id") or padre.get("channel_id")

    snippet = e.get("description")
    return DiscoverItem(
        video_id=video_id,
        title=title,
        uploader=str(uploader) if uploader else None,
        channel_id=str(channel_id) if channel_id else None,
        duration_sec=duration_sec,
        views=views_int,
        views_approx=views_approx,
        playlist_index=index,
        thumbnail=_thumbnail(e, video_id, unavailable),
        unavailable=unavailable,
        description_snippet=str(snippet) if snippet else None,
    )


# --------------------------------------------------------------------------- búsqueda


def _buscar(query: str, limit: int) -> list[DiscoverItem]:
    info = _extract(f"ytsearch{limit}:{query}")
    items: list[DiscoverItem] = []
    for e in info.get("entries") or []:
        if not e.get("id"):
            continue
        # ytsearch trae view_count exacto (medido: 26874, 762), no redondeado.
        items.append(_item_de(e, views_approx=False))
    return items


# --------------------------------------------------------------------------- listado


def _tanda(url: str, offset: int, limit: int, padre_canal: bool) -> tuple[dict[str, Any], list[DiscoverItem], int]:
    """Una tanda `[offset, offset+limit)` de una playlist/tab. Devuelve (padre, items,
    entries consumidas). yt-dlp es 1-based en playliststart/playlistend."""
    info = _extract(url, playliststart=offset + 1, playlistend=offset + limit)
    entries = list(info.get("entries") or [])
    requested = info.get("requested_entries") or []
    padre = info if padre_canal else None

    items: list[DiscoverItem] = []
    vistos: set[str] = set()
    for i, e in enumerate(entries):
        vid = e.get("id")
        if not vid or vid in vistos:
            # Una playlist puede repetir el mismo video: una tanda no trae repetidos.
            continue
        vistos.add(vid)
        index = int(requested[i]) if i < len(requested) else offset + i + 1
        items.append(_item_de(e, padre, views_approx=True, index=index))
    return info, items, len(entries)


def _siguiente(offset: int, consumidas: int, limit: int, total: int | None) -> int | None:
    if consumidas < limit:
        return None
    siguiente = offset + consumidas
    if total is not None and siguiente >= total:
        return None
    return siguiente


def _playlist(ref: str, offset: int, limit: int) -> DiscoverListResult:
    url = _ref_playlist(ref)
    info, items, consumidas = _tanda(url, offset, limit, padre_canal=False)
    total = info.get("playlist_count")
    return DiscoverListResult(
        kind="playlist",
        id=str(info.get("id") or parse_qs(urlparse(url).query)["list"][0]),
        title=str(info.get("title") or ""),
        uploader=info.get("uploader") or info.get("channel"),
        channel_id=info.get("channel_id"),
        url=info.get("webpage_url") or url,
        total=int(total) if total is not None else None,
        offset=offset,
        next_offset=_siguiente(offset, consumidas, limit, total),
        items=items,
    )


def _canal(ref: str, offset: int, limit: int) -> DiscoverListResult:
    channel_id, url = _ref_canal(ref)
    padre: dict[str, Any] = {}
    if not channel_id:
        # @handle, /c/, /user/: pedir solo el padre para saber el UC… (~0.5 s).
        padre = _extract(url, process=False)
        cid = padre.get("channel_id")
        if cid and _CHANNEL_ID_RE.match(str(cid)):
            channel_id = str(cid)

    if channel_id:
        # Playlist de uploads: mismas entries que el tab, pero con uploader/channel_id
        # en cada una y con playlist_count (el tab no trae ninguna de las dos cosas).
        uploads = f"https://www.youtube.com/playlist?list=UU{channel_id[2:]}"
        try:
            info, items, consumidas = _tanda(uploads, offset, limit, padre_canal=True)
        except Exception as exc:  # noqa: BLE001 — si la UU no existe, el tab es el respaldo
            if ytdl.error_kind(exc) in ("toolchain", "transient", "blocked"):
                # Bloqueado: el tab daría lo mismo y sería otro golpe a la IP marcada.
                raise
            log.warning("uploads %s no listable (%s): caigo al tab de videos", uploads, ytdl.error_text(exc))
        else:
            total = info.get("playlist_count")
            nombre = info.get("channel") or info.get("uploader") or padre.get("channel") or ""
            return DiscoverListResult(
                kind="channel",
                id=channel_id,
                title=str(nombre),
                uploader=str(nombre) if nombre else None,
                channel_id=channel_id,
                url=info.get("channel_url") or f"https://www.youtube.com/channel/{channel_id}",
                total=int(total) if total is not None else None,
                offset=offset,
                next_offset=_siguiente(offset, consumidas, limit, total),
                items=items,
            )

    # Respaldo: el tab de videos. Sin total, y uploader/channel_id salen del padre.
    tab = (f"https://www.youtube.com/channel/{channel_id}" if channel_id else url) + "/videos"
    info, items, consumidas = _tanda(tab, offset, limit, padre_canal=True)
    cid = info.get("channel_id") or channel_id
    nombre = info.get("channel") or info.get("uploader") or ""
    return DiscoverListResult(
        kind="channel",
        id=str(cid or info.get("id") or ""),
        title=str(nombre),
        uploader=str(nombre) if nombre else None,
        channel_id=str(cid) if cid else None,
        url=info.get("channel_url") or url,
        total=None,
        offset=offset,
        next_offset=_siguiente(offset, consumidas, limit, None),
        items=items,
    )


# --------------------------------------------------------------------------- endpoints


def _http_error(exc: BaseException, que: str) -> HTTPException:
    """Errores de yt-dlp → HTTP: referencia inválida 400, no disponible 404, toolchain 503,
    bot-check de YouTube 503 (la playlist/canal existe: es la IP la que está marcada, y
    no hay que mostrarlo como "borrado"), el resto 502."""
    kind = ytdl.error_kind(exc)
    text = ytdl.error_text(exc)
    if kind == "invalid":
        return HTTPException(status_code=400, detail=text)
    if kind == "blocked":
        return HTTPException(status_code=503, detail=ytdl.blocked_detail(exc))
    if isinstance(exc, _NotFound) or kind == "unavailable":
        return HTTPException(status_code=404, detail=f"{que} no disponible: {text}")
    if kind == "toolchain":
        return HTTPException(status_code=503, detail=text)
    return HTTPException(status_code=502, detail=f"yt-dlp falló con {que}: {text}")


async def _en_hilo(fn: Callable[[], T], que: str) -> T:
    """yt-dlp es bloqueante → threadpool, de a dos a la vez (bot-check)."""
    async with _SEM:
        try:
            return await asyncio.to_thread(fn)
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001 — degradar con un error claro para el front
            raise _http_error(exc, que) from exc


@router.get("/discover")
async def discover(
    q: str = Query(..., min_length=1, description="qué buscar en YouTube"),
    limit: int = Query(20, ge=1, le=_SEARCH_MAX),
) -> DiscoverResult:
    """Busca en YouTube sin gastar quota. `views` exactas, sin `playlist_index`."""
    items = await _en_hilo(lambda: _buscar(q, limit), f"la búsqueda {q!r}")
    return DiscoverResult(query=q, items=items)


@router.get("/discover/playlist")
async def discover_playlist(
    url: str = Query(..., min_length=2, description="URL de YouTube con ?list=, o el id (PL…)"),
    offset: int = Query(0, ge=0),
    limit: int = Query(_LIST_DEFAULT, ge=1, le=_LIST_MAX),
) -> DiscoverListResult:
    """Una tanda de una playlist, sin quota ni API key. `views` redondeadas
    (`views_approx`), `playlist_index` 1-based como cursor, borrados marcados."""
    _ref_playlist(url)  # 400 acá, antes de tocar la red
    return await _en_hilo(lambda: _playlist(url, offset, limit), "la playlist")


@router.get("/discover/channel")
async def discover_channel(
    url: str = Query(..., min_length=2, description="URL de canal, @handle o UC…"),
    offset: int = Query(0, ge=0),
    limit: int = Query(_LIST_DEFAULT, ge=1, le=_LIST_MAX),
) -> DiscoverListResult:
    """Una tanda de los uploads de un canal (más nuevo primero), sin quota ni API
    key. Cada item lleva uploader/channel_id aunque YouTube no lo ponga en la entry."""
    _ref_canal(url)  # 400 acá, antes de tocar la red
    return await _en_hilo(lambda: _canal(url, offset, limit), "el canal")
