"""
yt-dlp compartido: opciones base, chequeo de toolchain y reintentos.

Por qué existe: el 19-sep el path "Analizar audio" estaba roto en silencio. yt-dlp
viejo (2026.07) daba 403 en toda descarga; el nuevo (2026.08.19) necesita un runtime
JS para resolver el desafío de YouTube y, si no lo encuentra, tira "Requested format
is not available" — y la API Python defaultea a `deno`, que en esta máquina no está
(hay node). Nadie lo veía: `/health` decía ok y el error llegaba como un 502 genérico.

Acá vive todo lo que los dos consumidores de yt-dlp (dsp.py para bajar audio,
discover.py para buscar/listar sin quota) tienen que compartir:

- `ydl_opts(**extra)`   → opciones base con el runtime JS autodetectado (deno > node).
- `js_runtime()`        → ('node', '22.16.0') o None. Solo runtimes que yt-dlp soporte.
- `toolchain()`         → qué hay instalado y qué falta, con mensajes accionables.
- `ToolchainError`      → para cortar ANTES de tocar la red cuando falta algo (→ 503).
- `video_url(ref)`      → id / youtu.be / watch?v= → URL canónica de UN video (o `InvalidUrl`).
- `with_retry(fn)`      → reintenta solo los 403 / "unable to download" transitorios.
- `youtube_block()`     → el último bot-check de YouTube ("Sign in to confirm you're not a
                          bot"), con hora, mientras dure el cooldown. Para `/health`.

Lo que NO va acá: recorte con ffmpeg, DSP, ni ninguna decisión de dominio.
Ver docs/SOURCES.md y .claude/agents/dsp-analyst.md.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, TypeVar
from urllib.parse import parse_qs, urlparse

from yt_dlp.version import __version__ as YTDLP_VERSION

from .config import settings

log = logging.getLogger("crate.ytdl")

T = TypeVar("T")

# Versión mínima de yt-dlp que resuelve el desafío JS de YouTube (antes: 403 en todo).
YTDLP_MIN = "2026.08.19"

# Runtimes JS en el orden de prioridad de yt-dlp. Los mínimos son los que exige
# yt-dlp (yt_dlp/utils/_jsruntime.py: Deno 2.3.0, Node 22.0.0); se leen de ahí si
# se puede, y si esa API privada cambia quedan estos como respaldo.
_RUNTIME_ORDER: tuple[str, ...] = ("deno", "node")
_RUNTIME_MIN_FALLBACK: dict[str, tuple[int, ...]] = {"deno": (2, 3, 0), "node": (22, 0, 0)}
_RUNTIME_VERSION_RE: dict[str, str] = {"deno": r"^deno (\S+)", "node": r"^v(\S+)"}

_PIP_UPGRADE = "pip install -U yt-dlp yt-dlp-ejs"


class ToolchainError(RuntimeError):
    """Falta una pieza del sistema (runtime JS, ffmpeg, yt-dlp viejo). No es un fallo
    del análisis ni del video: el mensaje dice qué instalar. Los endpoints lo mapean a 503."""


class InvalidUrl(ValueError):
    """La referencia no es un video de YouTube (ni id, ni youtu.be, ni watch?v=). Se corta
    antes de tocar la red: yt-dlp no abre nada que no armemos acá. Los endpoints → 400."""


# Hosts desde los que aceptamos una URL de video. Cualquier otro host es InvalidUrl:
# el backend no es un open relay hacia yt-dlp.
_VIDEO_HOSTS = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"})
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
# Rutas de youtube.com que llevan el id en el path (además de /watch?v=).
_VIDEO_PATHS = ("shorts", "embed", "v", "live")


@dataclass(frozen=True)
class RuntimeProbe:
    """Un runtime JS encontrado en el PATH (o configurado), con su versión."""

    name: str
    path: str
    version: str
    supported: bool
    minimum: tuple[int, ...]


# --------------------------------------------------------------------------- helpers


def _setting(name: str) -> str:
    """Ajuste opcional: lo toma de `settings` si config.py ya lo declara; si no, del
    entorno (`CRATE_<NAME>`). Así ytdl.py no depende de que config.py cambie a la vez."""
    value = getattr(settings, name, None)
    if value is None:
        value = os.environ.get(f"CRATE_{name.upper()}", "")
    return str(value).strip()


def _version_tuple(version: str) -> tuple[int, ...]:
    """'2026.08.19' → (2026, 8, 19); '22.16.0' → (22, 16, 0). Tolera sufijos ('9.0-essentials')."""
    parts: list[int] = []
    for chunk in re.split(r"[.\-+]", version):
        m = re.match(r"\d+", chunk)
        if not m:
            break
        parts.append(int(m.group()))
    return tuple(parts)


@lru_cache(maxsize=16)
def _probe_version(path: str, pattern: str, arg: str = "--version") -> str | None:
    """Corre `<bin> --version` y saca la versión con `pattern`. Cacheado por ruta:
    cuesta ~100 ms por proceso y el binario no cambia mientras corre el server
    (`refresh()` limpia el cache si el usuario instala algo con el backend levantado)."""
    try:
        proc = subprocess.run(
            [path, arg],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.debug("no pude leer la versión de %s: %s", path, exc)
        return None
    out = (proc.stdout or "") + (proc.stderr or "")
    m = re.search(pattern, out.strip(), re.MULTILINE)
    return m.group(1).strip() if m else None


def _runtime_minimum(name: str) -> tuple[int, ...]:
    """Mínimo que exige la versión instalada de yt-dlp para ese runtime."""
    try:
        from yt_dlp.globals import supported_js_runtimes  # registrado por yt_dlp.__init__

        cls = supported_js_runtimes.value.get(name)
        minimum = getattr(cls, "MIN_SUPPORTED_VERSION", None)
        if isinstance(minimum, tuple) and minimum:
            return tuple(int(x) for x in minimum)
    except Exception:  # noqa: BLE001 — API privada de yt-dlp: si cambia, usamos el respaldo
        pass
    return _RUNTIME_MIN_FALLBACK[name]


def _configured_runtime() -> tuple[str, str | None] | None:
    """`CRATE_JS_RUNTIME=node` o `node:C:\\ruta\\node.exe` fuerza un runtime (útil en
    Windows cuando el binario no está en el PATH del proceso). Vacío = autodetectar."""
    raw = _setting("js_runtime")
    if not raw:
        return None
    # partition corta en el PRIMER ':', así que "node:C:\x\node.exe" deja la ruta entera.
    name, _, path = raw.partition(":")
    name = name.strip().lower()
    if name not in _RUNTIME_ORDER:
        log.warning("CRATE_JS_RUNTIME=%r no es deno ni node: se ignora y se autodetecta", raw)
        return None
    return name, (path.strip().strip('"') or None)


def _probe_runtime(name: str, path_hint: str | None = None) -> RuntimeProbe | None:
    path = path_hint or shutil.which(name)
    if not path:
        return None
    if os.path.isdir(path):
        found = shutil.which(name, path=path)
        if not found:
            return None
        path = found
    version = _probe_version(path, _RUNTIME_VERSION_RE[name])
    if version is None:
        return None
    minimum = _runtime_minimum(name)
    return RuntimeProbe(
        name=name,
        path=path,
        version=version,
        supported=_version_tuple(version) >= minimum,
        minimum=minimum,
    )


def _find_runtimes() -> list[RuntimeProbe]:
    """Todos los runtimes que hay (soportados o viejos), en orden de prioridad.
    Si hay uno configurado a mano, solo ese."""
    configured = _configured_runtime()
    if configured:
        probe = _probe_runtime(*configured)
        return [probe] if probe else []
    probes = (_probe_runtime(name) for name in _RUNTIME_ORDER)
    return [p for p in probes if p]


def ffmpeg_path() -> str | None:
    """Ruta a ffmpeg: CRATE_FFMPEG_PATH (archivo o carpeta) o el PATH. None si no hay."""
    configured = _setting("ffmpeg_path")
    if configured:
        if os.path.isdir(configured):
            return shutil.which("ffmpeg", path=configured)
        return configured if os.path.isfile(configured) else None
    return shutil.which("ffmpeg")


def _fpcalc_path() -> str | None:
    # Duplica a propósito la resolución de fingerprint.fpcalc_path(): importar
    # fingerprint arrastra dsp → librosa (lento) y cierra un ciclo con este módulo.
    configured = settings.fpcalc_path.strip()
    if configured:
        return configured if os.path.isfile(configured) else None
    return shutil.which("fpcalc")


def _ejs_version() -> str | None:
    try:
        import yt_dlp_ejs  # type: ignore[import-not-found]

        return str(getattr(yt_dlp_ejs, "version", "") or "instalado")
    except ImportError:
        return None


def refresh() -> None:
    """Olvida las versiones cacheadas (para un `GET /health?refresh=1` después de instalar algo).
    NO olvida el bot-check registrado: eso lo levanta una descarga que ande o el cooldown."""
    _probe_version.cache_clear()


def _cookiefile() -> str | None:
    """`CRATE_YTDLP_COOKIES` = ruta a un cookies.txt (formato Netscape, exportado del
    navegador). Es la salida al bot-check de YouTube cuando la IP quedó marcada. Vacío o
    inexistente = sin cookies (queda un warning si apunta a algo que no está)."""
    configured = _setting("ytdlp_cookies")
    if not configured:
        return None
    if os.path.isfile(configured):
        return configured
    log.warning("CRATE_YTDLP_COOKIES=%r no existe: yt-dlp corre sin cookies", configured)
    return None


def video_url(ref: str) -> str:
    """Normaliza la referencia a UN video: un id de 11 chars, `youtu.be/<id>`, o una URL de
    youtube.com (www/m/music) con `?v=<id>` o `/shorts|embed|v|live/<id>`
    → `https://www.youtube.com/watch?v=<id>`.

    Lo que no sea eso es `InvalidUrl` (→ 400): en particular una URL de playlist pura,
    que `noplaylist=True` NO frena (aplica solo a watch?v=…&list=…) y con `download=True`
    bajaría todos los videos de la lista antes de fallar.
    """
    ref = (ref or "").strip()
    if not ref:
        raise InvalidUrl("falta la URL del video")
    if _VIDEO_ID_RE.match(ref):
        return f"https://www.youtube.com/watch?v={ref}"
    if "." not in ref and "/" not in ref:
        # Un token suelto que no es un id de video (p.ej. un id de playlist PL…).
        raise InvalidUrl(
            f"{ref!r} no es un id de video (11 caracteres) ni una URL de YouTube "
            "(una playlist entera no se analiza; para minarla está /discover/playlist)"
        )
    raw = ref if "://" in ref else f"https://{ref}"
    try:
        u = urlparse(raw)
    except ValueError as exc:
        raise InvalidUrl(f"no entiendo {ref!r} como URL de video") from exc
    host = (u.hostname or "").lower()
    if host not in _VIDEO_HOSTS:
        raise InvalidUrl(
            f"solo se analizan videos de YouTube (youtube.com / youtu.be), no {host or ref!r}"
        )
    parts = [p for p in u.path.split("/") if p]
    vid = ""
    if host == "youtu.be":
        vid = parts[0] if parts else ""
    else:
        vid = (parse_qs(u.query).get("v") or [""])[0].strip()
        if not vid and len(parts) >= 2 and parts[0] in _VIDEO_PATHS:
            vid = parts[1]
    if not _VIDEO_ID_RE.match(vid):
        raise InvalidUrl(
            "pasá un video: watch?v=<id>, youtu.be/<id> o el id de 11 caracteres "
            "(una playlist entera no se analiza; para minarla está /discover/playlist)"
        )
    return f"https://www.youtube.com/watch?v={vid}"


# --------------------------------------------------------------------------- API


def js_runtime() -> tuple[str, str] | None:
    """El runtime JS que va a usar yt-dlp: ('node', '22.16.0') o None si no hay ninguno
    soportado. Prioridad deno > node (la misma que yt-dlp). Un runtime demasiado viejo
    cuenta como ausente acá; `toolchain()` sí lo nombra para poder decir "actualizá"."""
    for probe in _find_runtimes():
        if probe.supported:
            return probe.name, probe.version
    return None


def toolchain() -> dict[str, Any]:
    """Estado del toolchain, para `/health` y para los errores 503.

    Claves fijas del contrato: `yt_dlp {ok, version, min}`, `js_runtime {ok, name, version}`,
    `ffmpeg {ok, version}`, `fpcalc {ok}`. Cada componente trae además `problem` (texto
    accionable o None). Arriba: `ok` (se puede bajar Y recortar audio: yt-dlp + yt-dlp-ejs +
    runtime JS + ffmpeg; fpcalc es opcional, solo /identify) y `problems` (los textos
    de lo que falta para bajar y recortar, vacío si está todo).
    """
    ytdlp_ok = _version_tuple(YTDLP_VERSION) >= _version_tuple(YTDLP_MIN)
    ytdlp_problem = None if ytdlp_ok else (
        f"yt-dlp {YTDLP_VERSION} es viejo (mínimo {YTDLP_MIN}: antes YouTube devuelve 403 "
        f"en toda descarga). Actualizá con `{_PIP_UPGRADE}` dentro del venv del backend."
    )

    ejs = _ejs_version()
    ejs_problem = None if ejs else (
        "Falta el paquete yt-dlp-ejs (trae el resolvedor del desafío JS de YouTube; sin "
        f"él node no sirve). Instalalo con `{_PIP_UPGRADE}`."
    )

    runtimes = _find_runtimes()
    usable = next((p for p in runtimes if p.supported), None)
    js_problem: str | None = None
    if usable is None:
        old = [p for p in runtimes if not p.supported]
        configured = _configured_runtime()
        if old:
            p = old[0]
            minimum = ".".join(map(str, p.minimum))
            js_problem = (
                f"{p.name} {p.version} es demasiado viejo para yt-dlp (necesita {p.name} {minimum}+). "
                + (
                    "Actualizá node: `winget upgrade OpenJS.NodeJS.LTS` o https://nodejs.org (LTS 22+)."
                    if p.name == "node"
                    else "Actualizá deno: https://deno.com (2.3+)."
                )
            )
        elif configured:
            js_problem = (
                f"CRATE_JS_RUNTIME={_setting('js_runtime')!r} apunta a un {configured[0]} que no "
                "está o no responde a --version. Corregí la ruta o dejalo vacío para autodetectar."
            )
        else:
            js_problem = (
                "Falta un runtime JS para yt-dlp (sin eso YouTube responde 'Requested format is "
                "not available'). Instalá node 22+ (`winget install OpenJS.NodeJS.LTS` o "
                "https://nodejs.org) o deno 2.3+ (https://deno.com), y que quede en el PATH "
                "del proceso del backend; o apuntá CRATE_JS_RUNTIME=node:C:\\ruta\\node.exe."
            )

    ffmpeg = ffmpeg_path()
    ffmpeg_version = _probe_version(ffmpeg, r"^ffmpeg version (\S+)", "-version") if ffmpeg else None
    ffmpeg_problem = None if ffmpeg else (
        "Falta ffmpeg (recorta la ventana de audio a WAV para librosa/fpcalc). Instalalo con "
        "`winget install Gyan.FFmpeg` o desde https://ffmpeg.org, o apuntá CRATE_FFMPEG_PATH "
        "al ffmpeg.exe."
    )

    fpcalc = _fpcalc_path()
    fpcalc_problem = None if fpcalc else (
        "Falta fpcalc (Chromaprint), solo hace falta para /identify. Bajalo de "
        "https://github.com/acoustid/chromaprint/releases y poné la ruta al .exe en "
        "CRATE_FPCALC_PATH, o dejalo accesible desde el PATH."
    )

    problems = [p for p in (ytdlp_problem, ejs_problem, js_problem, ffmpeg_problem) if p]
    return {
        "ok": not problems,
        "yt_dlp": {"ok": ytdlp_ok, "version": YTDLP_VERSION, "min": YTDLP_MIN, "problem": ytdlp_problem},
        "yt_dlp_ejs": {"ok": ejs is not None, "version": ejs, "problem": ejs_problem},
        "js_runtime": {
            "ok": usable is not None,
            "name": usable.name if usable else None,
            "version": usable.version if usable else None,
            "path": usable.path if usable else None,
            # Lo que se vio aunque no sirva (p.ej. node 18): para que /health lo cuente.
            "found": [{"name": p.name, "version": p.version, "supported": p.supported} for p in runtimes],
            "problem": js_problem,
        },
        "ffmpeg": {"ok": ffmpeg is not None, "version": ffmpeg_version, "path": ffmpeg, "problem": ffmpeg_problem},
        "fpcalc": {"ok": fpcalc is not None, "path": fpcalc, "problem": fpcalc_problem},
        "problems": problems,
    }


def ensure_ready(*, ffmpeg: bool = True, fpcalc: bool = False) -> dict[str, Any]:
    """Corta ANTES de tocar la red si falta algo para bajar (y recortar) audio.

    Levanta `ToolchainError` con TODOS los problemas en un solo mensaje accionable.
    `ffmpeg=False` alcanza para descargas sin recorte; `fpcalc=True` lo exige (/identify:
    la API key de AcoustID la sigue chequeando fingerprint.ensure_available()).
    Devuelve el dict de `toolchain()` para que el caller no lo calcule dos veces.
    """
    tools = toolchain()
    needed = ["yt_dlp", "yt_dlp_ejs", "js_runtime"]
    if ffmpeg:
        needed.append("ffmpeg")
    if fpcalc:
        needed.append("fpcalc")
    problems = [tools[k]["problem"] for k in needed if tools[k]["problem"]]
    if problems:
        raise ToolchainError(" | ".join(problems))
    return tools


def ydl_opts(**extra: Any) -> dict[str, Any]:
    """Opciones base para `YoutubeDL(...)`. Todo lo que pases en `extra` pisa la base
    (p.ej. `noplaylist=False, extract_flat=True` para listar playlists; `format=...,
    outtmpl=...` para bajar).

    - `js_runtimes` apunta al runtime detectado con su ruta resuelta: yt-dlp usa exactamente
      el binario que probamos, no el primero que encuentre él (en Windows mira cwd primero).
      Si no hay ninguno se manda `{}` (explícito: nada de runtimes) y queda un warning en el
      log; el 503 lo da `ensure_ready()`, no esta función — listar playlists no necesita JS.
    - `remote_components` vacío: el JS lo trae yt-dlp-ejs (pip), no se baja nada de GitHub.
    - `logger` manda la salida de yt-dlp al logging de Python en vez de stderr.
    - `cookiefile` solo si `CRATE_YTDLP_COOKIES` apunta a un cookies.txt que existe
      (la salida al bot-check de YouTube).
    """
    runtimes: dict[str, dict[str, str]] = {}
    for probe in _find_runtimes():
        if probe.supported:
            runtimes[probe.name] = {"path": probe.path}
            break
    if not runtimes and "js_runtimes" not in extra:
        log.warning("yt-dlp sin runtime JS (deno/node): buscar/listar anda, bajar audio no")

    cookies = _cookiefile()
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "js_runtimes": runtimes,
        "remote_components": [],
        "logger": _YdlLogger(),
        # Sin códigos ANSI en los mensajes: el texto del error viaja al `detail` del 404/503.
        "color": "no_color",
        # Nunca escribimos al lado del audio: nada de .part huérfanos ni info.json.
        "writeinfojson": False,
        "overwrites": True,
        "noprogress": True,
    }
    if cookies:
        opts["cookiefile"] = cookies
    opts.update(extra)
    return opts


class _YdlLogger:
    """Adaptador logger para yt-dlp: sus mensajes van a `crate.ytdl` (debug/warning/error)."""

    def debug(self, msg: str) -> None:
        # yt-dlp manda por `debug` tanto lo de --verbose ("[debug] ...") como el progreso normal.
        log.debug("%s", msg)

    def info(self, msg: str) -> None:
        log.debug("%s", msg)

    def warning(self, msg: str) -> None:
        log.warning("%s", msg)

    def error(self, msg: str) -> None:
        log.error("%s", msg)


# --------------------------------------------------------------------------- errores


# Bot-check de YouTube: "Sign in to confirm you're not a bot. Use --cookies-from-browser
# or --cookies…". El video EXISTE; lo que pasa es que YouTube marcó la IP del backend.
# Se chequea ANTES que _UNAVAILABLE ("sign in to confirm" también está ahí, para el
# 'confirm your age', que sí es del video). No se reintenta: insistir alarga el bloqueo.
_BLOCKED = (
    "not a bot",
    "cookies-from-browser",
    "--cookies",
)

# Lo que YouTube dice cuando el video no existe / no se puede ver: no se reintenta y
# al usuario le corresponde un 404, no un 502.
_UNAVAILABLE = (
    "video unavailable",
    "video is unavailable",
    "private video",
    "has been removed",
    "video is not available",
    "no longer available",
    "not available in your country",
    "sign in to confirm",
    "members-only",
    "join this channel",
    "is not a valid url",
    "unsupported url",
    "incomplete youtube id",
    "has been terminated",
)

# Errores que suelen ser transitorios (YouTube rota urls firmadas, corta conexiones):
# un reintento con espera alcanza. 'unable to download' incluye los 403 al bajar.
_TRANSIENT = (
    "http error 403",
    "http error 429",
    "http error 5",
    "unable to download",
    "connection reset",
    "connection aborted",
    "timed out",
    "timeout",
    "remote end closed",
    "incompleteread",
    "temporary failure",
    "got error:",
)

# Con yt-dlp ≥ 2026.08 esto es casi siempre "no hay runtime JS" o EJS desactualizado.
_TOOLCHAIN = (
    "requested format is not available",
    "no supported javascript runtime",
    "js runtime",
    "challenge solver",
)


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_PREFIX_RE = re.compile(r"^(?:ERROR:\s*)?(?:\[[\w:+-]+\]\s*)?(?:[\w-]{11}:\s*)?", re.IGNORECASE)


def error_text(exc: BaseException) -> str:
    """El error de yt-dlp en una línea legible para el `detail` de un HTTPException:
    sin códigos ANSI, sin el prefijo 'ERROR: [youtube] <id>:', recortado a 300 chars."""
    lines = [ln.strip() for ln in _ANSI_RE.sub("", str(exc)).splitlines() if ln.strip()]
    text = lines[-1] if lines else exc.__class__.__name__
    return _PREFIX_RE.sub("", text, count=1)[:300]


def error_kind(exc: BaseException) -> str:
    """'invalid' (→ 400) | 'toolchain' (→ 503) | 'blocked' (→ 503) | 'unavailable' (→ 404)
    | 'transient' (→ reintentar) | 'other' (→ 502).

    Se decide por el texto porque yt-dlp envuelve todo en `DownloadError`/`ExtractorError`
    sin códigos. El orden importa: toolchain antes que unavailable ("Requested format is
    not available" no es un video caído); blocked antes que unavailable ("Sign in to
    confirm you're not a bot" no es un video caído, es la IP marcada, y 'sign in to
    confirm' también está en _UNAVAILABLE por el 'confirm your age'); y unavailable antes
    que transient (un video borrado puede decir también 'unable to download' y no
    queremos reintentarlo).
    """
    if isinstance(exc, InvalidUrl):
        return "invalid"
    if isinstance(exc, ToolchainError):
        return "toolchain"
    text = str(exc).lower()
    if any(s in text for s in _TOOLCHAIN):
        return "toolchain"
    if any(s in text for s in _BLOCKED):
        return "blocked"
    if any(s in text for s in _UNAVAILABLE):
        return "unavailable"
    if any(s in text for s in _TRANSIENT):
        return "transient"
    return "other"


def blocked_detail(exc: BaseException | None = None) -> str:
    """El `detail` accionable de un 503 por bot-check. El texto de yt-dlp va al final
    (sirve para el log), pero lo primero es lo que el usuario puede hacer."""
    text = f" ({error_text(exc)})" if exc is not None else ""
    return (
        "YouTube pide verificación para esta IP (bot-check): no es un problema del video. "
        "Esperá unas horas sin descargas masivas desde esta conexión, o exportá las cookies "
        "de tu navegador a un cookies.txt y apuntá CRATE_YTDLP_COOKIES a ese archivo"
        + text
    )


# --------------------------------------------------------------------------- bot-check


# Último bot-check visto, para que /health no diga `ok` mientras YouTube tiene marcada la
# IP. Lo levanta una descarga que ande (`clear_block()` desde dsp.download_audio) o el
# cooldown; listar playlists no lo levanta porque eso anda igual estando bloqueado.
_block_lock = threading.Lock()
_block: dict[str, Any] | None = None
_BLOCK_COOLDOWN_DEFAULT_SEC = 15 * 60


def _block_cooldown_sec() -> float:
    raw = _setting("youtube_block_cooldown_sec")
    try:
        return max(0.0, float(raw)) if raw else float(_BLOCK_COOLDOWN_DEFAULT_SEC)
    except ValueError:
        return float(_BLOCK_COOLDOWN_DEFAULT_SEC)


def note_block(exc: BaseException) -> None:
    """Registra un bot-check (llamado por `with_retry` cuando `error_kind` dice 'blocked')."""
    global _block
    with _block_lock:
        _block = {"ts": time.time(), "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "detail": error_text(exc)}
    log.error("YouTube bot-check: la IP quedó marcada (%s)", error_text(exc))


def clear_block() -> None:
    """Una descarga que anduvo: el bloqueo se levantó (o nunca fue de la IP)."""
    global _block
    with _block_lock:
        if _block is not None:
            log.info("YouTube bot-check: descarga ok, se levanta la marca")
        _block = None


def youtube_block() -> dict[str, Any] | None:
    """`{"blocked_at": iso, "age_sec": n, "detail": texto}` si hubo un bot-check hace menos
    del cooldown (`CRATE_YOUTUBE_BLOCK_COOLDOWN_SEC`, 15 min por defecto); si no, None.
    El cooldown es para que la UI no invite a reintentar al toque (insistir alarga el
    bloqueo), no una verdad sobre YouTube: pasado, /health vuelve a decir ok y el próximo
    intento real es el que decide."""
    with _block_lock:
        b = _block
    if b is None:
        return None
    age = time.time() - float(b["ts"])
    if age > _block_cooldown_sec():
        return None
    return {"blocked_at": b["at"], "age_sec": int(age), "detail": b["detail"]}


def with_retry(
    fn: Callable[[], T],
    tries: int = 3,
    backoff: Sequence[float] = (2, 5, 8),
) -> T:
    """Corre `fn()` y reintenta SOLO los errores transitorios (403 / 'unable to download' /
    cortes de red), esperando `backoff[i]` segundos entre intentos. Un video no disponible,
    un toolchain roto, un bot-check o cualquier otro error sale a la primera, sin esperar.
    El bot-check además queda registrado (`youtube_block()`), para /health.

    Lo que se midió el 19-sep: con 2/5/8 s los 403 esporádicos entre descargas encadenadas
    se resolvieron siempre en el segundo intento.
    """
    tries = max(1, int(tries))
    last: BaseException | None = None
    for attempt in range(tries):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — clasificamos por texto, ver error_kind
            last = exc
            kind = error_kind(exc)
            if kind == "blocked":
                note_block(exc)
            if kind != "transient" or attempt == tries - 1:
                raise
            wait = float(backoff[min(attempt, len(backoff) - 1)]) if backoff else 0.0
            log.warning(
                "yt-dlp: error transitorio (intento %d/%d), reintento en %.0fs: %s",
                attempt + 1,
                tries,
                wait,
                error_text(exc),
            )
            if wait > 0:
                time.sleep(wait)
    assert last is not None  # tries >= 1: o retornó o hay excepción
    raise last
