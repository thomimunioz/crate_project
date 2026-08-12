"""Shapes de request/response. Todo resultado de análisis lleva confidence."""
from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    url: str
    start_sec: int | None = None
    seconds: int | None = None
    # Aprovechar el mismo fragmento para identificar por huella (una descarga, dos usos).
    identify: bool = False


class IdentifyRequest(BaseModel):
    url: str
    start_sec: int | None = None
    seconds: int | None = None


class BpmResult(BaseModel):
    value: float
    confidence: float


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
    bpm: BpmResult | None = None
    key: KeyResult | None = None
    mood: MoodResult | None = None
    instruments: InstrumentsResult | None = None
    identification: IdentifyResult | None = None
    # Por qué no se pudo identificar, si se pidió (falta fpcalc o falta la key).
    identification_error: str | None = None


class DiscoverItem(BaseModel):
    """Lo mínimo que devuelve la búsqueda sin quota. La metadata rica va aparte."""
    video_id: str
    title: str
    uploader: str | None = None
    channel_id: str | None = None
    duration_sec: int | None = None
    views: int | None = None


class DiscoverResult(BaseModel):
    query: str
    items: list[DiscoverItem] = []
