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

Para `/identify` necesitás además **fpcalc** (Chromaprint): binarios en
https://github.com/acoustid/chromaprint/releases. Poné la ruta al `.exe` en `CRATE_FPCALC_PATH`
o dejalo accesible desde el PATH. Y una API key gratis de AcoustID en `CRATE_ACOUSTID_KEY`
(https://acoustid.org/new-application). Si falta cualquiera de las dos, `/identify` responde
**503 con el motivo** y `/analyze` sigue funcionando igual.

Copiá `../.env.example` a `../.env` (o seteá las `CRATE_*` en el entorno).

## Endpoints

- `GET /health` — ping.
- `GET /proxy?url=<encoded>` — relay con **allowlist** (`CRATE_PROXY_ALLOWLIST`). Nunca open relay.
- `POST /analyze` — `{ url, start_sec?, seconds?, identify? }` → baja un fragmento con yt-dlp, corre
  Librosa (BPM + key) y devuelve `{ bpm:{value,confidence}, key:{value,confidence} }`. Borra el
  fragmento. Con `identify: true` se baja **un solo** fragmento (el más largo de los dos) y el mismo
  archivo alimenta el DSP y la huella → el resultado suma `identification`.
- `POST /identify` — `{ url, start_sec?, seconds? }` → huella acústica (fpcalc) del fragmento y
  lookup en AcoustID. Devuelve candidatos con `score` (similitud de huella), `confidence` (nuestra,
  descontada por cuánto audio se huelló), `recording_mbid`, `artist`, `title` y `releases`.
  Provenance: `source: acoustid`, `method: fingerprint`.

## Notas

- El análisis es **opt-in y último recurso**: solo corre cuando el usuario aprieta "Analizar audio".
- Mood/instrumentos por audio (Essentia) queda como extensión — ver `.claude/agents/dsp-analyst.md`.
- La huella se calcula sobre el **arranque** del track (`CRATE_IDENTIFY_SECONDS`, 120s por defecto):
  es donde alinea con la huella de referencia de AcoustID. A AcoustID se le declara la duración del
  **track completo** (la que reporta la fuente), porque su índice filtra candidatos por duración.
- AcoustID: 3 req/seg por key. El backend serializa los lookups para no pasarse.
