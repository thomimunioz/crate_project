"""Shapes de request/response. Todo resultado de análisis lleva confidence."""
from typing import Literal

from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    url: str
    # Dónde arranca la ventana de BPM/key. None = el backend elige (60 s si el track dura
    # más de 150 s, si no el 20% de la duración: nunca la intro).
    start_sec: float | None = None
    seconds: int | None = None
    # Aprovechar la misma descarga para identificar por huella (una descarga, dos recortes).
    identify: bool = False


class IdentifyRequest(BaseModel):
    url: str
    start_sec: int | None = None
    seconds: int | None = None


class BpmAlternative(BaseModel):
    """Un candidato de tempo con la evidencia de audio que lo respalda (0..1)."""
    value: float
    support: float


class BpmWindow(BaseModel):
    """La ventana real que se analizó (segundos desde el arranque del track)."""
    start_sec: float
    seconds: int


class BpmResult(BaseModel):
    """
    BPM elegido por EVIDENCIA de audio, sin prior de gusto: `value` es el candidato con
    más support. El cliente es quien decide si lo pliega a su rango (affinity) — para eso
    están `alternatives` (todos los candidatos evaluados, ordenados por support, incluido
    el ganador) y `ambiguous` (los dos mejores están demasiado cerca: mirá las alternativas).
    """
    value: float
    confidence: float
    alternatives: list[BpmAlternative] = []
    ambiguous: bool = False
    window: BpmWindow | None = None
    # Versión del algoritmo (dsp.BPM_METHOD): el cliente sabe qué análisis viejos re-correr.
    method: str = "onset-ac/2"


class KeyResult(BaseModel):
    value: str
    confidence: float


class MoodResult(BaseModel):
    value: dict[str, list[str]]  # { feels: [...], textures: [...] }
    confidence: float


class InstrumentsResult(BaseModel):
    value: list[str]
    confidence: float


class IdentifyCandidate(BaseModel):
    """Un candidato de AcoustID. El score es de la huella; la confidence es nuestra."""
    acoustid: str
    score: float                      # similitud de huella que devuelve AcoustID (0..1)
    confidence: float                 # score ajustado por cuánto audio pudimos huellar
    recording_mbid: str | None = None  # MBID de grabación → engancha con MusicBrainz
    artist: str | None = None
    title: str | None = None
    releases: list[str] = []          # release groups (álbumes) donde aparece
    duration_sec: float | None = None  # duración de la grabación según MusicBrainz


class IdentifyResult(BaseModel):
    candidates: list[IdentifyCandidate] = []
    source: str = "acoustid"
    method: str = "fingerprint"
    fingerprint_seconds: int = 0      # cuánto audio entró en la huella
    lookup_duration_sec: int = 0      # duración que se le declaró a AcoustID


class AnalyzeResult(BaseModel):
    # `bpm`/`key` en None = la ventana no tenía pulso / tonalidad medible (silencio, fade).
    # Nunca se inventa un 0 BPM ni un "C major" con confianza 0: sin dato, sin valor.
    bpm: BpmResult | None = None
    key: KeyResult | None = None
    mood: MoodResult | None = None
    instruments: InstrumentsResult | None = None
    identification: IdentifyResult | None = None
    # Por qué no se pudo identificar, si se pidió (falta fpcalc o la key, o la huella /
    # AcoustID fallaron). El BPM/key se devuelven igual: la huella nunca tumba el análisis.
    identification_error: str | None = None
    # Duración del track completo según la fuente: para que la UI ubique la ventana.
    duration_sec: float | None = None


class DiscoverItem(BaseModel):
    """Lo mínimo que devuelve yt-dlp en modo flat (búsqueda, playlist o canal), sin
    quota. La metadata rica (descripción, tags, fecha) va aparte, por `videos.list`.

    Nada acá es una decisión de dominio: no se filtra basura ni se rankea. El cliente
    decide qué hacer con un borrado o con un mix de 2 horas.
    """
    video_id: str
    title: str
    uploader: str | None = None
    channel_id: str | None = None
    duration_sec: int | None = None
    views: int | None = None
    # Playlist/canal traen las views REDONDEADAS (945000, 1700): `views_approx=True`.
    # `ytsearch` las trae exactas (26874). Solo `videos.list` las pisa como exactas.
    views_approx: bool = False
    # Posición 1-based dentro de la playlist/canal (None en búsqueda). Sirve de cursor.
    playlist_index: int | None = None
    thumbnail: str | None = None
    # `[Deleted video]` / `[Private video]`: se devuelve con la marca, no se filtra.
    unavailable: bool = False
    # Solo `ytsearch` trae un recorte de la descripción (truncado con "..."): alcanza
    # para detectar `℗` o un link a Discogs temprano, no para el fuzzy.
    description_snippet: str | None = None


class DiscoverResult(BaseModel):
    query: str
    items: list[DiscoverItem] = []


class DiscoverListResult(BaseModel):
    """Una tanda de una playlist o de un canal (`GET /discover/playlist|channel`)."""
    kind: Literal["playlist", "channel"]
    id: str                           # id de playlist (PL…/UU…) o de canal (UC…)
    title: str
    uploader: str | None = None       # dueño de la playlist / nombre del canal
    channel_id: str | None = None     # UC… del dueño (None si YouTube no lo expone)
    url: str | None = None            # URL canónica (para "abrir en YouTube")
    # Cuántos hay en total. Playlists lo traen siempre; canales solo cuando se pudo
    # listar por su playlist de uploads (UU…), si no queda None.
    total: int | None = None
    offset: int = 0
    # Desde dónde pedir la próxima tanda; None cuando se terminó.
    next_offset: int | None = None
    items: list[DiscoverItem] = []
