# CRATE backend

FastAPI liviano: **proxy** (resuelve CORS y scraping) + **discovery con yt-dlp** (búsqueda y
listado de playlists/canales sin quota) + **worker de DSP** (Capa 2, opt-in).
No es el cerebro del producto — la lógica de dominio vive en el frontend. Ver `../docs/ARCHITECTURE.md`.

## Correr

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8787
```

## Requisitos del sistema

Buscar y listar playlists con yt-dlp (`/discover`) no necesita nada de esto. Bajar audio
para analizarlo, sí:

- **yt-dlp ≥ 2026.08.19 + yt-dlp-ejs** (van por `requirements.txt`). Las versiones
  anteriores devuelven **403** en toda descarga desde mediados de 2026. Si YouTube vuelve a
  cambiar: `pip install -U yt-dlp yt-dlp-ejs` dentro del venv.
- **Un runtime JS: node 22+ o deno 2.3+.** yt-dlp lo usa para resolver el desafío de
  YouTube; sin runtime dice "Requested format is not available" o baja formatos degradados.
  Windows: `winget install OpenJS.NodeJS.LTS` (o https://nodejs.org). El backend autodetecta
  deno primero y node después (`app/ytdl.py`); si el binario no está en el PATH del proceso,
  apuntalo con `CRATE_JS_RUNTIME=node:C:\Program Files\nodejs\node.exe`.
- **ffmpeg** en el PATH (o `CRATE_FFMPEG_PATH`): recorta la ventana a WAV mono 22050 para
  librosa y fpcalc. Windows: `winget install Gyan.FFmpeg` o https://ffmpeg.org.

Para ver qué encontró el backend y qué falta, con el texto de cómo arreglarlo:

```bash
python -c "from app.ytdl import toolchain; import json; print(json.dumps(toolchain(), indent=1))"
```

Ese mismo chequeo (`app/ytdl.py::toolchain()` / `ensure_ready()`) es el que `GET /health`
expone en `tools` y el que `/analyze` e `/identify` usan para responder **503 con el motivo**
antes de tocar la red, en vez de romperse en silencio.

Para `/identify` necesitás además **fpcalc** (Chromaprint): binarios en
https://github.com/acoustid/chromaprint/releases. Poné la ruta al `.exe` en `CRATE_FPCALC_PATH`
o dejalo accesible desde el PATH. Y una API key gratis de AcoustID en `CRATE_ACOUSTID_KEY`
(https://acoustid.org/new-application). Si falta cualquiera de las dos, `/identify` responde
**503 con el motivo** y `/analyze` sigue funcionando igual.

Copiá `../.env.example` a `../.env` (o seteá las `CRATE_*` en el entorno).

## Endpoints

- `GET /health` — `{ ok, tools }`: `ok` dice si se puede bajar y recortar audio; `tools` es
  `ytdl.toolchain()` (yt-dlp, yt-dlp-ejs, runtime JS, ffmpeg, fpcalc, con el texto de qué
  instalar si falta). `?refresh=1` vuelve a mirar el sistema.
- `GET /proxy?url=<encoded>` — relay con **allowlist** (`CRATE_PROXY_ALLOWLIST`). Nunca open relay.
- `GET /discover?q=<texto>&limit=20` (≤ 50) — búsqueda con yt-dlp `ytsearch`, **0 quota**, sin
  API key ni runtime JS. Devuelve `{ query, items: [DiscoverItem] }`; acá las `views` son exactas
  y viene un `description_snippet` truncado (alcanza para ver un `℗` o un link a Discogs).
- `GET /discover/playlist?url=<URL con ?list= o id PL…/UU…>&offset=0&limit=200` (≤ 500) y
  `GET /discover/channel?url=<URL, @handle o UC…>&offset=0&limit=200` — una **tanda** del
  listado flat (yt-dlp `extract_flat`, 0 quota). Respuesta `DiscoverListResult`:
  `{ kind: "playlist"|"channel", id, title, uploader, channel_id, url, total, offset,
  next_offset, items }`. `total` sale de `playlist_count` (en canales solo si se pudo listar
  su playlist de uploads `UU…`); `next_offset` es el cursor (`null` = terminó).
  Cada `DiscoverItem`: `{ video_id, title, uploader, channel_id, duration_sec, views,
  views_approx, playlist_index, thumbnail, unavailable }`. En flat las `views` vienen
  **redondeadas** (`views_approx: true`); los borrados/privados vienen con `unavailable: true`
  y no se filtran (decide el cliente); las entries de un canal heredan `uploader`/`channel_id`
  del padre. No trae descripción, fecha ni tags: eso lo pide el cliente a `videos.list`.
  Sin filtro de basura ni ranking acá: es dominio, va en el cliente.
  Errores: 400 referencia inválida o host que no es YouTube; 404 playlist/canal privado o
  inexistente; 503 toolchain o bot-check de YouTube (la lista existe, la IP está marcada); 502 el resto.
- `POST /analyze` — `{ url, start_sec?, seconds?, identify? }` → descarga temporal, recorte de la
  ventana, Librosa (BPM + key), borrado. Devuelve `bpm`, `key`, `duration_sec` (ver "DSP").
  Con `identify: true` la **misma descarga** da un segundo recorte desde el segundo 0 para la
  huella → el resultado suma `identification`.
- `POST /identify` — `{ url, start_sec?, seconds? }` → huella acústica (fpcalc) del recorte y
  lookup en AcoustID. Devuelve candidatos con `score` (similitud de huella), `confidence` (nuestra,
  descontada por cuánto audio se huelló), `recording_mbid`, `artist`, `title` y `releases`.
  Provenance: `source: acoustid`, `method: fingerprint`.

Errores de `/analyze` e `/identify` (el `detail` es para mostrarlo tal cual en la UI):

- **503** falta algo del toolchain (runtime JS, ffmpeg, yt-dlp viejo): `detail` dice qué instalar.
  Se corta ANTES de tocar la red.
- **404** el video no está (borrado, privado, geobloqueado): `detail` empieza con "video no disponible".
- **502** cualquier otra cosa (descarga cortada tras los reintentos, ffmpeg, DSP).

## DSP: cómo se analiza el audio

**Regla:** descarga temporal completa → recorte → borrado. **Nunca se sirve ni se guarda audio.**

1. `yt-dlp` baja `bestaudio` **entero** a `CRATE_TMP_DIR` con su downloader nativo (~4 MB, ~2 s).
   No se recorta en la descarga: `download_ranges` delega en ffmpeg y YouTube responde 403.
   Los 403 esporádicos se reintentan con espera 2/5/8 s (`app/ytdl.py::with_retry`).
2. `ffmpeg` hace uno o dos **recortes a WAV mono 22050** (`app/dsp.py::Downloaded.cut`):
   - BPM/key: la **ventana** `start_sec` + `seconds` (`CRATE_ANALYZE_SECONDS`, 45 s). Si el
     cliente no manda `start_sec`, arranca a los **60 s** (pasada la intro) o al **20%** si el
     track dura ≤ 150 s. La ventana real vuelve en `bpm.window`.
   - huella (solo con `identify`): desde el segundo 0, `CRATE_IDENTIFY_SECONDS` (120 s).
3. Librosa lee el WAV (~1 s) y estima BPM y tonalidad.
4. `finally`: se borran el original y todos los recortes, falle lo que falle.

**BPM por evidencia, sin prior de gusto.** El backend no sabe qué música escucha el usuario:
devuelve lo que el audio respalda y el cliente decide.

```json
"bpm": {
  "value": 76.0, "confidence": 0.61,
  "alternatives": [{"value": 76.0, "support": 1.0}, {"value": 152.0, "support": 0.61}, {"value": 38.0, "support": 0.12}],
  "ambiguous": true,
  "window": {"start_sec": 60, "seconds": 45},
  "method": "onset-ac/2"
}
```

- `alternatives`: todos los candidatos evaluados (picos de la autocorrelación del onset y sus
  ×0.5/×2, ajustados al pico real con interpolación parabólica), ordenados por `support`.
  El ganador también está en la lista. `support` es el puntaje **relativo al ganador**
  (`score / best_score`): el elegido siempre trae `1.0` y los demás cuánto le arriman; no
  es una probabilidad (para eso está `confidence`).
- `value`: el candidato con más evidencia (support + voto de backbeat si está prendido).
- `ambiguous`: el segundo candidato está demasiado cerca del primero. Es la señal para que
  la UI ofrezca "÷2 / ×2" y para que el cliente aplique su rango (`core/tempo.ts`), con
  provenance `inferred` y razón en el Why this.
- `method`: versión del algoritmo, para saber qué análisis viejos re-correr.

La calibración vive en `tools/bpm_calibrate.py` (ver `tools/README.md`): mide el algoritmo
contra `docs/benchmarks/2026-09-19-digging-a-mano/bpm_octave_dataset.json` (247 temas con la
octava corregida a oído) sin volver a bajar audio.

## Notas

- El análisis es **opt-in y último recurso**: solo corre cuando el usuario aprieta "Analizar audio".
- La descarga completa es un detalle de transporte (lo único que YouTube deja bajar sin 403), no
  una feature: el archivo vive en `tmp/` los segundos que tarda el recorte y se borra siempre.
- Mood/instrumentos por audio (Essentia) queda como extensión — ver `.claude/agents/dsp-analyst.md`.
- La huella se calcula sobre el **arranque** del track (`CRATE_IDENTIFY_SECONDS`, 120s por defecto):
  es donde alinea con la huella de referencia de AcoustID. A AcoustID se le declara la duración del
  **track completo** (la que reporta la fuente), porque su índice filtra candidatos por duración.
- AcoustID: 3 req/seg por key. El backend serializa los lookups para no pasarse.
