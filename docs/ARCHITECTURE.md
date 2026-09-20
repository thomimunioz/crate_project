# Arquitectura

## Vista general

```
┌─────────────────────────── FRONTEND (browser, React PWA) ───────────────────────────┐
│                                                                                      │
│  tres puertas ──► cavarTanda: normalize → enrich → score ──► ResultCard + Why this?   │
│   runSearch (fan-out por escena, core/queries.ts)  │        │                         │
│   abrirVeta → proximaTanda → cavarVeta (vetas)     │        └─ core/score.ts          │
│   importPlaylist (propias → Saved con tag)         │           + affinity + tempo     │
│                                                    └─ core/ytHints.ts → fuzzy.ts →    │
│                                                       sources/musicbrainz → discogs   │
│  db/crateIndex.ts ── IndexedDB (Dexie): seen (con contexto) / saved / analyzed /      │
│                      rejected + analyses (BPM crudo, alternativas) + affinity          │
└──────┬───────────────────────┬──────────────────────────────┬───────────────────────┘
       │ CORS / scraping        │ discovery sin quota            │ botón "Analizar audio"
       ▼                        ▼                                ▼
  ┌──────────────────────── BACKEND (FastAPI, liviano) ─────────────────────────────┐
  │  /proxy      relay con allowlist (Discogs, MusicBrainz, Archive)                 │
  │  /discover   yt-dlp ytsearch (0 quota)                                           │
  │  /discover/playlist · /discover/channel   listado flat paginado (0 quota)        │
  │  /analyze    descarga temporal completa → ffmpeg recorta → Librosa → borra       │
  │  /identify   misma descarga → fpcalc → AcoustID                                   │
  │  /health     { ok, tools }: yt-dlp, yt-dlp-ejs, runtime JS, ffmpeg, fpcalc        │
  │  app/ytdl.py: toolchain, reintentos, clasificación de errores (503/404/502)      │
  └─────────────────────────────────────────────────────────────────────────────────┘
```

## Dónde corre cada cosa

| Cosa | Dónde | Por qué |
|---|---|---|
| Normalización, enrichment, scoring, affinity, prior de tempo | **Cliente (TS)** | Metadata-first; instantáneo; el gusto es del usuario, no del server |
| Crate-index (seen/saved/analyzed/rejected + analyses + affinity) | **Cliente (IndexedDB/Dexie)** | Miles de registros, async, privado, sin DB paga |
| Llamadas que CORS bloquea + scraping | **Backend proxy** | El navegador no las deja hacer |
| Búsqueda y listado de playlists/canales con yt-dlp | **Backend** | yt-dlp es Python; no gasta quota de la API |
| Análisis de audio (DSP) y huella | **Backend worker** | No se puede extraer audio de YouTube en el cliente |

> El backend es **fino**: proxy + listador + DSP. Devuelve **evidencia** (candidatos de BPM con
> support, `ambiguous`, views redondeadas marcadas como tales). El cerebro (entidades, score,
> affinity, elección de octava) vive en el cliente. Nada de gusto personal en Python.

## El pipeline (Capa 1)

`frontend/src/pipeline/index.ts` orquesta. Hay **tres puertas** que convergen en la misma
tanda (`cavarTanda`: normalize → enrich → score, a lo sumo `ENRICH_LIMIT` = 24 por tanda):

- **`runSearch`**: fan-out de queries por escena (`core/queries.ts::planificarQueries`) → ids
  vía `GET /discover` (yt-dlp `ytsearch`, 0 quota; fallback `search.list` si el backend no
  está) → `videos.list` para snippet + stats → anti-basura → orden de digging.
- **Vetas**: `abrirVeta(veta)` lista por `/discover/playlist|channel` (flat, 0 quota, sin
  tope) → `listarMas` pagina → `proximaTanda` elige N no vistos (canales conocidos primero)
  → `cavarVeta` pide `videos.list` **solo para esa tanda** y corre
  `cavarTanda(..., { origen: 'veta' })`. Cobertura total del pool a lo largo de las tandas, con
  `seen` como cursor y `mining.visto/total` en el store (`useCrateStore.mine/mineMore`; la URL
  se pega en `Vetas.tsx`, `parseVetaRef`). Una playlist ajena entra como `seen`.
- **`importPlaylist`**: playlist PROPIA → `saveFromPlaylist` como Saved con el nombre como tag.
  Una playlist ajena NUNCA entra por acá: es veta (`seen`), no crate.

Y dentro de `cavarTanda`:

1. **normalize(items)** → `Candidate[]`: `extractHints` (`core/ytHints.ts`: link a Discogs,
   Topic con ℗/`Released on:`/reedición, créditos por rol, convenciones de título, uploader
   como artista) + `splitArtistTitle`/`cleanTitle` (`core/fuzzy.ts`). Los hints van con
   `method: 'parsed'` y confidence; no se escriben en los campos de catálogo.
2. **enrich(candidates)** → pista dura confirma sin fuzzy; si no, MusicBrainz identifica a
   nivel grabación → Discogs enriquece el release (créditos, sello, país, want/have).
   Throttleado por fuente y cacheado una semana (`db/cache.ts`). Render progresivo.
3. **scoreAll(tracks, query, affinity, ctx)** → `computeCrateScore(track, query, affinity,
   weights, ctx)` + `reasons` (positivas y `↓`). `cavarTanda` arma el `ctx` con
   `contextoDe(query, opts)`: escenas de `escenasDe(query)` y origen de la puerta
   (`'busqueda'` en `runSearch`, `'veta'` en `cavarVeta`). Con `origen: 'veta'` la obscuridad
   pesa la mitad (el pool ya está curado) y la época sale de la escena del plan.
4. **filtrar `Seen`** → `knownSourceIds()` por índice, antes de enriquecer. `markSeen` guarda
   el contexto (query, sesión, origen) para que `hitRatePorQuery()` mida solo.

## Capa 2 (opt-in): "Analizar audio"

1. UI dispara `POST /analyze { url, start_sec?, seconds?, identify? }` (`api/backend.ts`).
2. Backend, antes de tocar la red: `ytdl.ensure_ready()` → si falta yt-dlp al día, runtime JS
   o ffmpeg, **503 con el motivo** (`GET /health` lo muestra igual).
3. `dsp.download_audio`: **descarga temporal completa** de `bestaudio` con yt-dlp (downloader
   nativo, con `js_runtimes` autodetectado; ~4 MB, ~2 s), reintento 2/5/8 s solo en 403/
   transitorios. Video caído → **404**; otro → **502**. El recorte por `download_ranges` (lo de
   antes) delegaba en ffmpeg y daba 403 en silencio.
4. `Downloaded.cut(start, seconds)`: ffmpeg recorta la ventana a WAV mono 22050 (librosa lo
   carga en ~1 s contra 18 s del webm). Ventana default `smart_start`: 60 s si dura > 150 s,
   si no el 20%; se acomoda al final del track. Con `identify: true`, un segundo recorte 0–120 s
   para la huella: **una descarga, dos usos**.
5. Librosa → `bpm_from_onset` (candidatos de la autocorrelación + ×0.5/×2, jerarquía métrica,
   backbeat por paridad, confidence calibrada como probabilidad) + key por chroma. Devuelve
   `bpm: { value, confidence, alternatives[{value, support}], ambiguous, window, method }`,
   `key`, `duration_sec`. **Sin prior de gusto**: `value` es lo que la evidencia de audio
   sostiene. Mood/instrumentos siguen `null` (Essentia, F2).
6. Todo (original, recortes, `.part`) se borra en `finally`, falle lo que falle. ~4 s por tema.
7. Cliente (`db/crateIndex.ts::saveAnalysis`): `tempo.ts::foldBpm` elige la octava con el prior
   del usuario (`tasteTempoRange(affinity)`, default 58–115) entre las `alternatives`; si pliega,
   la ficha lleva `audio_analysis/inferred` con razón y el crudo + alternativas + ventana quedan
   en la tabla `analyses`. `setBpmManual` (÷2/×2, `user/manual`) es lo que recalibra el prior.
   Estado `analyzed` (o `saved` si ya lo era).

Medido (`backend/tools/bpm_calibrate.py` sobre 247 pares): octava correcta 51% → 75% backend
solo; 82% plegado a 58–115; el correcto está entre las alternativas el 98% de las veces.

Lote "analizar estos N guardados": próximo (hoy dos `/analyze` en paralelo bajan a la vez).

## PWA

`vite-plugin-pwa` + `public/manifest.webmanifest`. Instalable en desktop y mobile; funciona
"de donde sea". El crate-index es local al dispositivo (por ahora; sync multiusuario = futuro).

## Requisitos del sistema (backend)

Buscar y listar con yt-dlp no necesita nada de esto. Bajar audio para analizar, sí:

- `yt-dlp >= 2026.08.19` + `yt-dlp-ejs` (en `requirements.txt`). Antes: 403 en toda descarga.
- Runtime JS: **node 22+** o **deno 2.3+** (autodetección deno > node en `app/ytdl.py`;
  override `CRATE_JS_RUNTIME=node:C:\ruta\node.exe`). Sin yt-dlp-ejs, node no alcanza.
- **ffmpeg** en el PATH o `CRATE_FFMPEG_PATH`.
- **fpcalc** + `CRATE_ACOUSTID_KEY` solo para `/identify`.

`GET /health?refresh=1` → `{ ok, tools }` con versión, ruta y el texto de qué instalar.
Detalle: `backend/README.md`.

## Seguridad / privacidad

- Keys del usuario: las de front van en `.env` (VITE_*) y quedan en su build local; el proxy
  agrega throttling y allowlist para no exponer un proxy abierto.
- El proxy **nunca** es open relay: solo hosts en `CRATE_PROXY_ALLOWLIST`. `/discover/*` tampoco:
  solo URLs de YouTube armadas por el backend (host ajeno → 400 antes de tocar la red).
- El análisis hace una descarga temporal completa, la recorta, la borra en `finally` y nunca la
  sirve; no redistribuye audio. `raw` de YouTube no se persiste en Dexie.
