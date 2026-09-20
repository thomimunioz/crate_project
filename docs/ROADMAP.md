# Roadmap

## F1 — El núcleo (el 80% del valor)

**Objetivo:** que cavar una veta o buscar `japanese city pop 1982` traiga cosas que Thomas
**guarda**, a una tasa comparable a la del digging a mano, y que sienta que encontró algo
que no hubiera encontrado normal. La vara no son las views: es el **hit rate** (abajo).

Flujo mínimo:

```
Input (query + filtros + fuentes)  ó  una veta (canal / playlist de otro digger)
   → Discovery         yt-dlp sin quota (ytsearch, flat playlist/canal) + Internet Archive
   → Normalization     hints del snippet + split artista/título + fuzzy
   → Enrichment        MusicBrainz identifica → Discogs enriquece (provenance por dato)
   → Scoring           filterMatch + rarity + obscurity + sourceQuality + historical + affinity
   → Results           CRATE SCORE · Why this? (también las razones ↓) · ▶ Preview · ♡ Save · 🧠 Analyze
   → Personal crate    Seen / Saved / Analyzed / Rejected   (IndexedDB)
```

### Ya hecho (verificado en el código al 20-sep-2026)

- Entorno levantando: frontend, backend, ffmpeg, `.env` único en la raíz. Los secretos
  de Discogs viven en el backend, que inyecta la auth en el proxy: un `VITE_` se
  inlinea en el bundle público.
- Entity model + provenance + confidence (`core/entities.ts`, `core/provenance.ts`).
- Seen / Saved / Analyzed / Rejected + **"no me muestres lo que ya vi"** por id de fuente.
- CRATE Score + **Why this?** explicable, incluidas las razones que bajan (`↓`).
- Enrichment throttleado por fuente (`sources/throttle.ts`) y cacheado una semana en
  IndexedDB (`db/cache.ts`).
- Vista del crate con filtro local, y sacar del crate revirtiendo la affinity.
- **Import de playlists propias de YouTube** como semilla, con el nombre de cada
  playlist como tag propio.
- **Cruce contra catálogo reconstruido** (14% → 57% → 72% con pistas duras): snippet →
  MusicBrainz a nivel grabación → Discogs para enriquecer. Ver `docs/SOURCES.md`.
- **Render progresivo**: las fichas se pintan al instante y se completan en el lugar.
- **Fan-out de queries por escena** (`core/queries.ts::planificarQueries`, lanes
  jerga/sello/nativo/artista/descriptor) en vez de concatenar strings.
- **Discovery sin quota**: `GET /discover` (yt-dlp `ytsearch`, fallback a `search.list` si el
  backend no está), y `GET /discover/playlist` / `GET /discover/channel` (listado flat,
  paginado de a 200, 0 unidades). `backend/app/discover.py`.
- **Huella acústica** (`POST /identify` + `identifyByFingerprint`), opt-in por ficha.
- **Toolchain honesta** (`backend/app/ytdl.py`): versión mínima de yt-dlp, runtime JS
  (node 22+/deno 2.3+), ffmpeg, fpcalc; `GET /health` lo expone y `/analyze` responde 503
  con el motivo. Antes "Analizar" fallaba en silencio con 403.
- **"Analizar audio" que anda de nuevo**: descarga temporal completa → recorte con ffmpeg →
  Librosa → borrado. BPM con `alternatives` + `ambiguous` + ventana, sin prior de gusto en el
  backend. Octava correcta 51% → 75% sin prior (`backend/tools/bpm_calibrate.py`).
- **El prior de tempo en el cliente** (`core/tempo.ts::foldBpm`, rango 58–115 aprendible
  de `bpmBuckets`): 82% de octava correcta (85% con 58–135); el plegado se guarda como
  `inferred` con razón y el crudo queda en la tabla `analyses`.
- **Hints del snippet ampliados** (`core/ytHints.ts`): `Released on:`, reediciones, créditos
  por rol, 8 convenciones de título de canales digger, uploader como artista. Medido con
  `frontend/scripts/hintsHarness.ts`: artista parseado 39% → 52% sobre 1.958.
- **Canales curadores y ruido como datos** (`core/canales.ts`, 38 + 10): curador suma a
  `sourceQuality` con razón; ruido baja la affinity. Nunca obscurity.
- **Score recalibrado** contra el benchmark (`frontend/scripts/scoreBench.ts`): obscurity
  penaliza mainstream en vez de premiar pocas views; época por escena; affinity por dato.
  AUC sobre el pool 0.42 → 0.66.
- **Crate-index v3** (`db/crateIndex.ts`): índices por `sourceIds`/`tags`, `seen` con contexto
  (query, sesión, origen) → `hitRate()` / `hitRatePorQuery()`; `skipFor` ("no para esta
  búsqueda", distinto de rechazar); `save(track, { tags })`; `setBpmManual`.
- **Vetas desde la UI, cavadas enteras**: `Vetas.tsx` acepta pegar una playlist, canal,
  @handle o id (`parseVetaRef`); `useCrateStore.mine/mineMore` → `abrirVeta` → `listarMas` →
  `proximaTanda` → `cavarVeta` (sin tope), por tandas de 24 no vistos con `seen` como cursor;
  `mining.visto/total/quedan` en el `Transporte` de `App.tsx` y el botón "seguir cavando".
  `markSeen` con contexto (`origen: 'veta'`, `queryText: veta:<nombre>`).
- **Score con contexto**: `cavarTanda` arma `{ escenas, origen }` con `contextoDe(query, opts)`
  (`'busqueda'` en `runSearch`, `'veta'` en `cavarVeta`) y lo pasa a `scoreAll`.
- **AnalyzePanel con evidencia**: ventana analizada, marca de "ambiguo", alternativas y el
  botón **÷2 / ×2** → `setBpmManual` (`user/manual`). `analyzeAudio` propaga el `detail` del
  503/404 (`BackendError`).
- **ResultCard**: razones `↓` (`esRazonNegativa`), "~1,7k views" cuando `viewsApprox`, y el
  ✕ "no para esta búsqueda" (`skipFor`) al lado de ♡ guardar y ⊘ rechazar.
- **Hints nuevos consumidos en el pipeline**: `normalize` toma artista/título/año de
  `hints.titleHints` (prioridad hints > split > canal, `artistFromChannel` al final);
  `enrichOne` reintenta MusicBrainz con `artistAlias`/`titleAlias` (kanji ↔ romaji), usa los
  créditos por rol del Topic y la política de año para reediciones (`anioDudoso`);
  `proximaTanda` ordena con `origen: 'veta'`.
- Estética base (vinilo japonés 70s).

### Sí o sí en F1 (lo que falta de verdad)

1. **Datos del usuario desde la app**: importar sus 5 playlists como Saved con tag, y que
   guardar/rechazar/corregir pase por la app para que el hit rate y el prior se midan solos.
2. Snapshot de `videos.list` de los 1.958 ids del benchmark (~40 unidades) para medir los
   hints sobre descripciones reales multilínea (hoy 175 planas).
3. Lote "analizar estos N guardados" con throttle (hoy dos `/analyze` en paralelo bajan a
   la vez y arriesgan 403). Acotado a `saved`: nunca promueve `seen` a `analyzed`.

**Fuentes F1:** YouTube (API + yt-dlp) · Discogs · MusicBrainz · Internet Archive · AcoustID.

**NO en F1:** Spotify, Bandcamp, SoundCloud, Soulseek, web search, ML sofisticado,
lenguaje natural, sync multiusuario. (Diseñar sin cerrarles la puerta, pero no construirlos.)

## Cómo se cava una veta (método validado a mano el 19-sep-2026)

El 19-sep se cavaron 10 playlists ajenas ("Samples Vol. 00–09", canal DIGGING, 1.958 temas)
sin la app, con Claude + agentes, y Thomas escuchó todo: **206 sugeridas, 109 guardadas
(53%)**. Costó ~4M tokens y ~60 min. La app tiene que hacer esto sola; cada paso del
método ya tiene (o le falta) su función:

| paso del método | en la app |
|---|---|
| listar la playlist entera con `--flat-playlist`, sin quota | `GET /discover/playlist` / `channel` (hecho) → `abrirVeta` / `listarMas` (hecho; se pega la URL en `Vetas.tsx`) |
| sacar lo que ya tenía y los duplicados | `knownSourceIds` + `hideSeen` (hecho); `claveDeObraDe` por obra en `sumarAlPool` (hecho) |
| **leer TODO**: la joya no se anuncia en el título, grep no sirve | cobertura total por tandas de `ENRICH_LIMIT` = 24 no vistos, sin recorte por título (`proximaTanda` + `cavarVeta` → `useCrateStore.mineMore`, hecho) |
| descartar solo basura dura (karaoke, tutorial, full album de 40 min) | `esBasura` (hecho). Lo personal (anime OST) va en `canales.ts` rol `ruido` |
| verificar año (℗, ojo reediciones) y artista | `extractHints` con `Released on:` + `reissue` (hecho); MB → Discogs (hecho) |
| verificar BPM medido, en la octava correcta | `/analyze` con `alternatives` (hecho) + `foldBpm` con el prior del cliente (hecho) + ÷2/×2 en `AnalyzePanel` → `setBpmManual` (hecho) |
| 3 lentes + crítico → ranking con vara alta y "why" de una línea | `planificarQueries` + `computeCrateScore` + `reasons` (positivas y `↓`) (hecho) |
| entrega con links y marcas; él guarda y redistribuye | Saved con tag de colección + `skipFor` (hecho: ♡ / ✕ / ⊘ en `ResultCard`) |

Lo que se aprendió y cambió el diseño:
- **Una playlist ajena entra como `seen`, nunca como `saved`** (a diferencia de la propia):
  importarla ensuciaría el crate y la affinity.
- **En una veta el portero no usa obscuridad** (`origen: 'veta'`): el pool ya está curado y
  lo de pocas views es basura mal titulada. Lo guardado tiene mediana 25k views.
- **Quién lo subió es la señal más fuerte sin catálogo** (canal del que ya guardó: 16–22% de
  guardado contra 3%), seguida de la duración (4–7 min). Ambas entran a `sourceQuality`.
- El flat no trae descripción ni fecha: `videos.list` (1 unidad / 50) se pide **solo para la
  tanda que se va a enriquecer**.

## Cómo se mide

**hit rate = guardados / sugeridos**, por lista y por sesión. Baseline a mano (19-sep):
80s 55/94 = 58% · SOUL 17/30 = 57% · R&B 10/30 = 33% · city pop 11/22 = 50% · fusion
16/30 = 53% · **total 109/206 = 53%**. Datos en `docs/benchmarks/2026-09-19-digging-a-mano/`.

Contra ese benchmark corren tres harnesses, y **cada cambio se reporta antes/después**:

| qué | comando | mide | hoy |
|---|---|---|---|
| ranking | `cd frontend && npx tsx scripts/scoreBench.ts` | AUC y precisión@30 contra `labels.json` | pool AUC 0.66, p@30 7/30; sugeridos AUC 0.59 |
| parseo | `cd frontend && npm run hints` | % con artista/año, basura, guardados que caerían (tiene que ser 0) | artista 52%, año 15%, basura 22/1.958, guardados caídos 0 |
| octava | `cd backend && python tools/bpm_calibrate.py eval` | % de octava correcta sobre 247 pares | 75% backend solo, 82% con prior 58–115, 85% con 58–135 |

En la app, `hitRatePorQuery()` (`db/crateIndex.ts`) calcula mostradas/guardadas/rechazadas
por búsqueda a partir de `seen` con contexto: es el número real, sin scripts, apenas Thomas
guarde y rechace desde la app en vez de desde YouTube.

Techo honesto: dentro de una shortlist ya curada, la metadata separa poco (AUC ~0.59); ahí
decide el sonido. Nunca vamos a llegar al 100%, pero cada red nueva vuelve al bench con más
peces etiquetados.

## F2 — Ampliar la red

- Spotify (solo referencia), búsqueda web general (Brave/SerpAPI), Bandcamp (scraping), Freesound opcional.
- Mejores modelos de mood/instrumentos por audio (Essentia; hoy vienen `null`).
- Affinity más fina (prior de tempo por escena, negativos aprendidos); primeras sugerencias
  "creo que esto te puede interesar".
- Candidatos ×1.5 / ÷1.5 y detección de feel ternario en el DSP: los errores que quedan en
  fusion son swing/tresillo (3:2), no octava.
- Búsqueda en lenguaje natural (traducción query → filtros).

## F3 — Lo pesado

- Soulseek (P2P, backend dedicado), SoundCloud.
- Eventual multiusuario (auth, quotas por usuario, sync del crate, affinity por usuario:
  `canales.ts` y el prior de tempo pasan a ser datos por persona).

## Principio de fases

Cada fase entrega algo **usable** antes de sumar complejidad. No agregar 25 features:
cerrar bien el núcleo, obsesionarse con la **calidad de resultados** (medida, no estimada),
y recién ahí ampliar.
