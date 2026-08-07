# CRATE backend

FastAPI liviano: **proxy** (resuelve CORS y scraping) + **worker de DSP** (Capa 2, opt-in).
No es el cerebro del producto — la lógica de dominio vive en el frontend. Ver `../docs/ARCHITECTURE.md`.

## Correr

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8787
```

Necesitás **ffmpeg** en el PATH (para que yt-dlp recorte el fragmento y librosa decodifique).
En Windows: `winget install Gyan.FFmpeg` o descargalo de ffmpeg.org.

Copiá `../.env.example` a `../.env` (o seteá las `CRATE_*` en el entorno).

## Endpoints

- `GET /health` — ping.
- `GET /proxy?url=<encoded>` — relay con **allowlist** (`CRATE_PROXY_ALLOWLIST`). Nunca open relay.
- `POST /analyze` — `{ url, start_sec?, seconds? }` → baja un fragmento con yt-dlp, corre Librosa
  (BPM + key) y devuelve `{ bpm:{value,confidence}, key:{value,confidence} }`. Borra el fragmento.

## Notas

- El análisis es **opt-in y último recurso**: solo corre cuando el usuario aprieta "Analizar audio".
- Mood/instrumentos por audio (Essentia) queda como extensión — ver `.claude/agents/dsp-analyst.md`.
