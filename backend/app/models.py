"""Shapes de request/response. Todo resultado de análisis lleva confidence."""
from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
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


class AnalyzeResult(BaseModel):
    bpm: BpmResult | None = None
    key: KeyResult | None = None
    mood: MoodResult | None = None
    instruments: InstrumentsResult | None = None
