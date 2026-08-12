"""CRATE backend — FastAPI. Proxy (CORS/scraping) + análisis de audio (opt-in)."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
def health() -> dict[str, bool]:
    return {"ok": True}
