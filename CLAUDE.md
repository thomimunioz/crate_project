# CRATE — Contexto para Claude

> Este archivo lo lee Claude Code automáticamente al abrir el proyecto. Es el
> onboarding: leélo entero antes de tocar nada. El detalle de cada tema vive en
> `docs/`. Los agentes especializados viven en `.claude/agents/`.

---

## Qué es CRATE (en una línea)

**Un buscador de crate-digging que construye tu propio índice mientras buscás.**

Rastrea la web abierta —discos reales de otra gente, no sample packs— para tirarte
**joyas ocultas** que probablemente no hubieras encontrado buscando normalmente,
filtrables por key, BPM, mood e instrumentos.

Lema de trabajo: **"The internet is the crate. Dig deeper. Find what nobody else found."**

El usuario (Thomas) es beatmaker de hiphop: boombap clásico → drumless moderno,
estética Griselda / Roc Marciano, mucho soul, jazz fusion, city pop, MPB, quiet
storm, library music, piano, 80s. CRATE está hecho para *ese* oído.

---

## La obsesión del producto (leé esto dos veces)

El mayor riesgo de CRATE **no es técnico, es la calidad de resultados.**

Podés tener la arquitectura más linda del mundo y que el usuario busque
`70s soul 75-90 BPM Rhodes` y reciba 500 temas genéricos que ya escuchó 40 veces.
Ahí muere el producto.

Toda decisión de discovery y scoring se mide contra **una** pregunta:

> **"¿Encontré algo que probablemente no hubiera encontrado buscando normal?"**

Si CRATE logra eso → hay producto. Si solo junta metadata de YouTube + Discogs →
es un buscador lindo y nada más.

**Cómo se mide:** *hit rate* = guardados / sugeridos, sobre lo que Thomas escucha de
verdad. No "cuántas views tiene". El primer número real está en
`docs/benchmarks/2026-09-19-digging-a-mano/` (53% a mano sobre 206 sugerencias).

---

## El oído de Thomas, medido (19–20 sep 2026, n=206 sugeridos / 1.958 en el pool)

Es affinity de UN usuario con fecha y n, no verdad universal; el detalle y los datos
están en `docs/benchmarks/2026-09-19-digging-a-mano/README.md`.

- **Tempo:** casi nunca > ~115 BPM real. El DSP lee la octava de arriba (95 de 120 crudos
  > 115 eran el doble); el rango 58–115 vive en el cliente (`core/tempo.ts`), no en el backend.
- **Mainstream no:** millones de views casi nunca se guardan aunque encajen (Whitney, Isleys,
  Patti Austin); Manhattans y Herb Alpert son la excepción. Lo guardado tiene mediana ~25k views.
- **Quién lo subió pesa:** de un canal del que ya guardó, guarda 16–22% contra 3% del resto; los
  4–7 min concentran lo guardado; < 3 min casi nunca. Es calidad de FUENTE, no obscuridad.
- **La década no es rígida** si la escuela es la misma (quiet storm 90–92, "TOP"). Y "no
  encaja en esta lista" no es rechazo: redistribuye entre sus colecciones.
- **Ruido para él, no para todos:** OST de anime/videojuegos, covers de videojuegos, vaporwave.
  Vive en `core/canales.ts` (rol `ruido`) + `TEMAS_DE_RUIDO_PERSONAL` y lo aplica la affinity.
  Karaoke, tutorial y "full album" > 20 min sin forma "Artista - Tema" son basura universal
  (`esBasura`, `core/queries.ts`).

---

## Qué NO es (límites duros)

- **No** es un agregador de sample packs. Nada de Splice, Tracklib, Loopcloud, Loopmasters.
- **No** descarga ni "captura" audio para el usuario. El flujo es **descubrir + preview**;
  el usuario salta a la fuente y consigue el audio por su cuenta. (El backend sí baja audio
  temporalmente para calcular BPM/key/huella, y lo borra: nunca se sirve.)
- **No** es multiusuario todavía. Es una herramienta **personal** (usa las API keys del
  usuario). Pero la arquitectura se diseña para poder abrirlo a otros beatmakers a futuro.
- **No** trata a YouTube como su base de datos. YouTube es **fuente de descubrimiento**;
  CRATE es dueño de la **entidad musical normalizada** (ver Entity Model).

---

## Principio rector: dos capas (el backend es el último recurso)

- **Capa 1 — en el browser (instantáneo, metadata-first).** Meta-search + text-mining +
  cruce contra Discogs/MusicBrainz. De acá sale casi todo: año, género, estilo, mood,
  rareza, **instrumentos (vía créditos de Discogs)** y BPM/key **si vienen taggeados** en
  el título/tags.
- **Capa 2 — opt-in, último recurso (DSP en backend).** El botón **"Analizar audio"** manda
  UN solo track a analizar: yt-dlp hace una **descarga temporal completa** del audio → ffmpeg
  recorta la ventana a WAV → Librosa calcula BPM/key con confidence → se borra todo en
  `finally`. **Nunca se sirve audio al usuario.** Nada pesado corre sin que el usuario lo dispare.
  El backend devuelve **evidencia** (`bpm.alternatives` + `ambiguous`), no gusto: la octava la
  elige el cliente con el prior del usuario (`core/tempo.ts`).

> Nota real: aunque la filosofía es "todo en el browser", **igual necesitamos un backend
> liviano** (FastAPI) desde el Tier 0 por tres razones: **CORS** (algunas fuentes y todo lo
> que sea scraping se bloquean desde el navegador), la **extracción de audio de YouTube**
> (no se puede en el cliente) y **yt-dlp como discovery sin quota** (`ytsearch` y listado
> flat de playlists/canales, `backend/app/discover.py`). El backend es un proxy fino +
> worker de DSP + listador, no el cerebro.

---

## Cuatro decisiones de arquitectura que NO se negocian (vienen de la revisión)

1. **Entity model:** `Source Item → Candidate → Music Entity (Recording / Release / Track) → Enriched`.
   CRATE posee la entidad canónica normalizada. Ver `docs/ENTITY_MODEL.md`.
2. **Provenance por dato:** cada dato tiene `{ value, source, method, confidence, updatedAt }`.
   Nunca mezclamos "metadata confirmada" con "metadata inferida/analizada". Se muestra
   siempre de dónde salió (`84 BPM · del título` vs `86 BPM · analizado` vs `soulful · inferido`).
   Ver `docs/ENTITY_MODEL.md` y `frontend/src/core/provenance.ts`.
3. **Estados Seen / Saved / Analyzed / Rejected.** El índice principal = `Saved + Analyzed`.
   `Seen` es historial/cache. **Feature clave de F1: "no me muestres lo que ya vi".**
4. **CRATE Score formal + "Why this?".** El score es explicable, nunca un numerito mágico.
   Ver `docs/CRATE_SCORE.md`.

---

## CRATE Score (el corazón del producto)

No es "rareza + pocas views". Es un intento de responder *"¿qué tan probable es que esto
sea una joya que todavía no encontraste?"*. Componentes:

```
CRATE SCORE
├── filter match          ¿pega con lo que pediste?
├── rarity               ¿qué tan rara es la OBRA (catálogo/prensado)? → Discogs want/have
├── obscurity            ¿qué tan difícil es ENCONTRARLA? → views, recomendación, titulado
├── metadata richness    ¿tenemos con qué trabajarla? (credits, año, sello)
├── source quality       ¿la fuente es confiable / buen rip?
├── historical relevance ¿sweet spot de época/escena?
└── personal affinity    ¿pega con TU crate (lo que venís guardando)?
```

**Rarity ≠ Obscurity ≠ Discovery value** — son tres cosas distintas, no las colapses.
Una canción con 200 views puede ser una joya rarísima o una mierda mal titulada.
Detalle y fórmula: `docs/CRATE_SCORE.md`. Implementación: `frontend/src/core/score.ts`.

Dos cosas medidas el 20-sep que cambiaron el score (ver `docs/CRATE_SCORE.md`):
- **Obscurity ya no premia pocas views**: penaliza lo mainstream. Meseta hasta 100k views y
  cae desde ahí (0,85 en 300k, 0,45 en 1M, 0 en 10M; `CURVA_VIEWS` en `score.ts`); la razón
  `↓ … esto ya lo conocés` aparece desde 500k. Dentro de una veta curada, lo de < 1k views se
  guardó al 2%: eran OST, karaoke y mal titulado.
- **Canal curador = source quality**, nunca obscurity: dice de quién lo subió, no de la obra.

Cada resultado muestra un **"Why this?"** con los motivos concretos, también los que
**bajan** el score (prefijo `↓`, `esRazonNegativa`):

```
✦ Strong dig — 75
1982 · 84 BPM · Rhodes · strings
Why this?
 • subido por Soultwinz, curador que ya te dio 3 temas
 • 1982 · época de quiet storm (1977–1987)
 • 100% match con tu crate
 • ↓ 2,3M views: esto ya lo conocés
```

---

## Taxonomía de mood (chica y a propósito)

Nada de campos libres tipo "happy/sad/chill". Taxonomía cerrada, útil para un beatmaker:

- **Energy:** 1 ─ 5
- **Feel:** laid-back · groovy · dreamy · dark · melancholic · uplifting · warm · tense
- **Texture:** dusty · clean · lush · raw · lo-fi · psychedelic · organic

Combinás: `dusty + melancholic + laid-back`. Ver `docs/TAXONOMY.md` y `frontend/src/core/taxonomy.ts`.
El modelo de filtros se diseña pensando en **búsqueda en lenguaje natural a futuro**
("soul brasileño de los 70, lento, con Rhodes y medio melancólico" → filtros), aunque eso NO va en F1.

---

## Stack técnico (ya decidido)

**Frontend** — `frontend/` · React 18 + Vite + TypeScript, PWA.
- Estado async / cache de queries: **TanStack Query**. Estado local: **Zustand**.
- **Crate-index local: IndexedDB vía Dexie.js** (miles de registros estructurados, async, sin server). NO LocalStorage.
- Estilos: **Tailwind** + design tokens propios (paleta/tipografías CRATE).
- El **core de dominio corre en el cliente** (entities, scoring, taxonomy, fuzzy, affinity) → metadata-first.

**Backend** — `backend/` · Python + **FastAPI**.
- Proxy fino con allowlist (resuelve CORS y scraping). `app/proxy.py`.
- Discovery sin quota con **yt-dlp**: `GET /discover` (`ytsearch`), `/discover/playlist` y
  `/discover/channel` (listado flat, paginado de a 200). `app/discover.py`.
- Worker de DSP: **yt-dlp** (descarga temporal completa) + **ffmpeg** (recorte a WAV) +
  **Librosa** (BPM/key) [+ Essentia opcional para mood/instrumentos, todavía null]. `app/dsp.py`,
  `app/analyze.py`. Huella acústica: `app/fingerprint.py` + `app/identify.py`.
- Toolchain en un solo lugar: `app/ytdl.py` (versión mínima de yt-dlp, runtime JS, ffmpeg,
  fpcalc, reintentos, clasificación de errores). `GET /health` lo expone en `tools`.
- Devuelve resultados con **confidence** y provenance `audio_analysis`; el BPM viene con
  `alternatives` + `ambiguous` y **sin prior de gusto**.

**Fuzzy matching:** `frontend/src/core/fuzzy.ts` — normaliza títulos falopa de YouTube
(`T. Yamashita ~ Sparkle (1982) [Vinyl Rip] HQ`) y hace match tolerante contra Discogs
(Levenshtein + limpieza de ruido). Es CRÍTICO para que el cruce no se rompa.

---

## Mapa del repo

```
crate_project/
├── CLAUDE.md              ← este archivo
├── README.md             ← quickstart
├── docs/                 ← toda la spec y el diseño (leer para el detalle)
│   ├── SPEC.md           ← spec de producto (v0.2, con todo integrado)
│   ├── ENTITY_MODEL.md   ← Source Item → Recording → Release → Track + provenance
│   ├── CRATE_SCORE.md    ← el score explicable + Why this?
│   ├── TAXONOMY.md       ← mood/feel/texture/energy + instrumentos + géneros
│   ├── SOURCES.md        ← mapa de fuentes, quotas, CORS, gotchas, fase
│   ├── ARCHITECTURE.md   ← data flow, dónde corre cada cosa, IndexedDB, DSP
│   ├── ROADMAP.md        ← qué está hecho, qué falta, cómo se cava una veta y cómo se mide
│   └── benchmarks/       ← datos reales congelados (19-sep-2026: pool, labels, BPM, canales)
├── .claude/agents/       ← 5 subagentes especializados (ver abajo)
├── frontend/             ← React + Vite + TS (PWA)
│   ├── scripts/          ← harnesses (hintsHarness, scoreBench) que leen docs/benchmarks
│   └── src/
│       ├── core/         ← dominio (entities, provenance, taxonomy, score, affinity, tempo,
│       │                    fuzzy, ytHints, queries, scenes, canales)
│       ├── sources/      ← clients por fuente (youtube, discogs, musicbrainz, archive)
│       ├── pipeline/     ← discover → normalize → enrich → score
│       ├── db/           ← Dexie crate-index (seen/saved/analyzed/rejected + analyses)
│       ├── state/        ← stores Zustand
│       ├── api/          ← cliente del backend (analyze, identify, discover, proxy)
│       └── ui/           ← componentes (ResultCard, AnalyzePanel, FilterBar, Vetas, ...)
└── backend/              ← FastAPI (proxy + discovery yt-dlp + DSP)
    ├── app/              ← main, config, models, proxy, ytdl, discover, analyze, dsp,
    │                        identify, fingerprint
    └── tools/            ← calibración a mano (bpm_calibrate.py contra el benchmark)
```

---

## Cómo correrlo

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

**Backend**
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8787
```

Copiá `.env.example` → `.env` y completá las keys (YouTube Data API, Discogs token).
En dev, Vite proxea `/api` → `http://localhost:8787` (ver `vite.config.ts`).

**Requisitos del backend (los reales, verificados el 20-sep-2026).** Buscar y listar con
yt-dlp no necesita nada de esto; bajar audio para "Analizar" sí:
- **yt-dlp ≥ 2026.08.19 + yt-dlp-ejs** (van en `requirements.txt`). Las versiones anteriores
  devuelven 403 en toda descarga desde mediados de 2026. Si vuelve a romperse:
  `pip install -U yt-dlp yt-dlp-ejs` en el venv.
- **Un runtime JS: node 22+ o deno 2.3+** (no 18: yt-dlp 2026.08 exige 22). Sin yt-dlp-ejs,
  node no resuelve el desafío de YouTube. Autodetección en `backend/app/ytdl.py`; override
  con `CRATE_JS_RUNTIME=node:C:\ruta\node.exe`.
- **ffmpeg** en el PATH (o `CRATE_FFMPEG_PATH`): recorta la ventana a WAV mono 22050.
- **fpcalc** (Chromaprint) + `CRATE_ACOUSTID_KEY` solo para `/identify`.

`GET /health` devuelve `{ ok, tools }` con qué hay, qué falta y cómo arreglarlo; `/analyze`
responde **503 con el motivo** antes de tocar la red si falta algo. Detalle: `backend/README.md`.

> Estado actual (20-sep-2026): **F1 funcionando, medido contra el oído real y
> recalibrado.** El pipeline (discover → normalize → enrich → score) corre entero,
> con render progresivo, throttling y cache. Hay un benchmark congelado en
> `docs/benchmarks/2026-09-19-digging-a-mano/` (1.958 temas de 10 playlists ajenas,
> 206 sugerencias, 109 guardadas por Thomas) y tres harnesses que lo leen:
> `frontend/scripts/hintsHarness.ts` (parseo), `frontend/scripts/scoreBench.ts`
> (ranking) y `backend/tools/bpm_calibrate.py` (octava del BPM).
>
> **Cómo se identifica una obra, en orden de fuerza:**
> 1. **Pistas duras del snippet de YouTube** (`core/ytHints.ts`) — link a Discogs
>    en la descripción, o canal `- Topic` con la metadata del distribuidor (`℗`,
>    `Released on:`, con detección de reedición para no tomar el ℗ 2007 de un LP de
>    1985 como año de la obra). Es un id o un dato de catálogo, no una
>    interpretación: confirma sin fuzzy. Las convenciones de título de los canales
>    digger (8 formas, `parseTitleConventions`) se parsean con `method: 'parsed'`
>    y confidence 0.6–0.7; `normalize` (`pipeline/index.ts`) las consume como
>    `hints.titleHints` (artista/título/año con prioridad hints > split > canal,
>    `artistFromChannel` al final) y `enrichOne` reintenta MusicBrainz con
>    `artistAlias`/`titleAlias` (kanji ↔ romaji) y usa los créditos por rol del Topic.
> 2. **MusicBrainz** (`sources/musicbrainz.ts`) — única fuente que busca a nivel
>    GRABACIÓN, que es el nivel de un título de YouTube.
> 3. **Discogs** (`sources/discogs.ts`) — enriquece el disco ya identificado con
>    créditos por instrumento, sello, país y want/have.
> 4. **Huella acústica** (`POST /identify`, AcoustID) — opt-in por ficha, para kanji
>    y títulos sueltos donde el texto no tiene con qué.
>
> Números medidos (agosto, ~80 temas de sus playlists): 14% → 57% con MusicBrainz →
> Discogs → **72% identificado** sumando las pistas duras del snippet (46% se identifica
> sin fuzzy); 68% con want/have, 52% con créditos. Tabla en `docs/SOURCES.md`. Sobre el pool del 19-sep
> (1.958, solo título + uploader + 175 descripciones): artista parseado 39% → **52%**;
> en Topic con descripción, año de la OBRA correcto 72/78 y créditos por rol 54/78.
>
> **La quota de YouTube ya no es el cuello de botella.** `search.list` (100 unidades)
> se reemplazó por `GET /discover` (yt-dlp `ytsearch`, 0 unidades, con fallback a la
> API si el backend no está); una playlist de 200 se lista en ~1,5 s y un canal de
> 1.845 uploads en 10 tandas de 200 (o 4 de 500) sin gastar nada (`/discover/playlist`,
> `/discover/channel`).
> Lo único que sigue costando quota es `videos.list` (1 unidad cada 50) para la
> descripción/fecha/tags de la tanda que se va a enriquecer: el flat no las trae.
> **El cuello de botella ahora es identificar la obra** con lo que trae el flat.
>
> **El oído decide en el cliente.** El score se recalibró contra el benchmark:
> AUC sobre el pool 0.42 → **0.66**, precisión@30 1/30 → 7/30 (`docs/CRATE_SCORE.md`).
> El DSP pasó de 51% a **75% de octava correcta sin prior**, y a **82%** cuando el
> cliente pliega con el rango 58–115 (`core/tempo.ts`; 85% con 58–135, que recupera el
> fusion > 115); en el 98% de los casos el BPM correcto está entre las `alternatives`
> que manda el backend.
>
> **La UI ya está cableada a todo eso:**
> - **Vetas por URL:** `Vetas.tsx` acepta pegar una playlist, canal, @handle o id
>   (`parseVetaRef`) y `useCrateStore.mine/mineMore` la cava ENTERA por tandas de 24 no
>   vistos (`abrirVeta` → `listarMas` → `proximaTanda` → `cavarVeta`), con `mining.visto/total`
>   en el `Transporte` de `App.tsx` y el botón "seguir cavando · quedan N". Entra como `seen`.
> - **Score con contexto:** `cavarTanda` arma `{ escenas, origen }` con `contextoDe(query, opts)`
>   (`'busqueda'` en `runSearch`, `'veta'` en `cavarVeta`).
> - **÷2 / ×2** en `AnalyzePanel` → `crateIndex.setBpmManual` (`user/manual`), con ventana
>   y marca de "ambiguo"; `analyzeAudio` propaga el `detail` del 503/404.
> - **ResultCard:** razones `↓` (`esRazonNegativa`), "~1,7k views" cuando `viewsApprox`, y
>   el ✕ "no para esta búsqueda" (`skipFor`, distinto de rechazar).
>
> **Lo próximo, en orden** (detalle en `docs/ROADMAP.md`):
> 1. **Más datos de Thomas, desde la app:** importar sus 5 playlists como Saved con tag,
>    guardar/rechazar en la app (para que `hitRatePorQuery()` mida solo), corregir la
>    octava a mano. Cada corrección `userSet` es un caso de prueba nuevo.
> 2. Snapshot de `videos.list` de los 1.958 ids del benchmark (~40 unidades) para medir
>    los hints sobre descripciones reales y no sobre 175.
> 3. Lote "analizar estos N guardados" con throttle, acotado a `saved` (hoy dos `/analyze`
>    en paralelo bajan a la vez y arriesgan 403).

---

## Los 5 agentes (`.claude/agents/`)

- **crate-scout** — inteligencia de digging: arma queries astutas por escena/época/sello
  para sacar joyas ocultas, y define los casos de prueba. Sabe de la estética (boombap,
  soul, city pop, MPB, quiet storm, library). Mantiene los DATOS de digging:
  `core/scenes.ts` (escenas, épocas, sobreexpuestos) y `core/canales.ts` (curadores y ruido).
- **source-integrator** — implementa/mantiene los clients de fuentes, CORS/proxy, manejo de
  quota, discovery con yt-dlp (`backend/app/discover.py`, `ytdl.py`), los hints del snippet
  (`core/ytHints.ts`) y el fuzzy matching / normalización de entidades.
- **dsp-analyst** — dueño del path de "Analizar audio": yt-dlp + ffmpeg + Librosa/Essentia,
  detección de BPM/key/mood/instrumentos con confidence y evidencia (alternativas), sin prior
  de gusto en el backend.
- **score-tuner** — dueño del CRATE Score, la separación rarity/obscurity/discovery,
  la affinity personal (por dato, según provenance), el prior de tempo del cliente
  (`core/tempo.ts`), el "Why this?" y la validación contra el benchmark.
- **digger-ux** — dueño de la PWA React, la estética (vinilo japonés 70s), el ResultCard
  con score + Why this?, el AnalyzePanel con confidence, y los flujos seen/saved/analyzed/rejected.

---

## Convenciones para trabajar acá

- **Metadata-first:** antes de mandar algo al backend, exprimí todo lo que se pueda sacar de
  texto y catálogos. El DSP es opt-in y último recurso.
- **Provenance siempre:** ningún dato entra al índice sin `source + method + confidence`.
  No inventes valores "seguros".
- **CRATE es dueño de la entidad:** las fuentes se normalizan hacia la entidad canónica; no
  ates la lógica a la forma de una fuente puntual.
- **Nada de guardar basura:** `Seen` es cache; solo `Saved`/`Analyzed` forman el crate real.
- **El score es explicable:** si agregás una señal al score, positiva o negativa, agregá su
  razón al "Why this?".
- **El backend no es el cerebro:** nada de gusto personal en Python. Devuelve evidencia con
  confidence; el cliente decide con la affinity. El gusto de Thomas es DATO (con fecha y n),
  no regla: la arquitectura tiene que poder abrirse a otro oído.
- **Medí antes de tocar:** si cambiás hints, score o DSP, corré el harness que corresponde
  contra `docs/benchmarks/` y reportá antes/después. Nada de "a ojo".
- Escribí TypeScript tipado (nada de `any` gratis) y comentarios en el idioma del código vecino.

## Casos de prueba (validación de F1)

**El criterio es el hit rate, no las views.** El motor anda si lo que sugiere se guarda a
una tasa comparable a la del digging a mano (53% total, 58% en 80s) y si, dentro de un
pool, lo guardado queda arriba (AUC > 0.5 y subiendo; hoy 0.66 sobre 1.954). Se mide con:
- `cd frontend && npx tsx scripts/scoreBench.ts` — AUC y precisión@30 contra `labels.json`.
- `cd frontend && npm run hints` — cobertura de artista/año/basura sobre `pool.json`.
- `cd backend && python tools/bpm_calibrate.py eval` — octava del BPM contra 247 pares.
- En la app: `hitRatePorQuery()` (`db/crateIndex.ts`) sobre lo que Thomas guarda/rechaza.

Queries de referencia para probar a mano (lo que traen tiene que sonar a joya, no a
"ya lo escuché 40 veces"):
- `80s quiet storm`
- `japanese city pop 1982`
- `70s brazilian MPB rhodes melancholic`
- `soul jazz rhodes 75-90 bpm minor`
- `library music cinematic strings 1974`

Y el caso real: cavar una playlist de "Samples Vol." del canal DIGGING y comparar contra
`docs/benchmarks/2026-09-19-digging-a-mano/labels.json`.

Detalle de nombre y branding: quedó **CRATE**. Mundo visual: crates, etiquetas, fichas,
stickers, sellos, timestamps, polvo, vinilos japoneses 70s (texturas vintage, tonos cálidos
desvanecidos, grano cinematográfico). Ver `docs/SPEC.md`.
