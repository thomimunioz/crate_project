# CIERRE — 19/20 sep 2026: del digging a mano a la app

Rama **`feature/digging-a-mano`** (sobre `develop`), **sin commitear**: 45 archivos modificados
(+6.385 / −877) y nuevos `backend/app/ytdl.py`, `backend/tools/`, `frontend/scripts/`,
`frontend/src/core/canales.ts`, `frontend/src/core/tempo.ts`, `docs/benchmarks/2026-09-19-digging-a-mano/`.
`npm run typecheck` y `npm run build` pasan; `import app.main` pasa; el backend real respondió
`/health`, `/discover/playlist`, `/discover/channel` y `/analyze`.

## Qué se hizo (y qué midió cada cosa)

| Área | Antes | Después |
|---|---|---|
| **DSP** (`dsp.py`, `analyze.py`, `identify.py`, `ytdl.py`) | "Analizar audio" muerto (403, sin runtime JS); octava correcta 51% (reproducido sobre el benchmark) | Descarga nativa + recorte ffmpeg + borrado; `/health` con toolchain; errores 404/503/502 con detail; BPM devuelve **alternativas con evidencia** y `ambiguous`. Octava: **74.9% backend solo, 82.2% con el rango 58–115 aplicado por el cliente**; la respuesta correcta está entre las alternativas en 98%. Harness `backend/tools/bpm_calibrate.py` (cache local, corre en 5 s). |
| **Discovery** (`discover.py`) | Solo `ytsearch` | `GET /discover/playlist` y `/discover/channel` sin quota, con `uploader/channel_id` propagados, `views_approx`, `playlist_index`, paginado. Playlist de 200 en 1,5 s; canal de 5.351 videos paginado. |
| **Hints** (`ytHints.ts`, `canales.ts`, `queries.ts`) | Topic mal parseado 0/78; artista detectado 38,9% del pool | Topic 78/78 (título, artista=canal, álbum 83%, año 94%, reedición detectada); artista 51,9%; convenciones de título de canales digger (país/género/año); 48 canales (38 curadores, 10 ruido personal) como **datos**; `esBasura` solo con lo universal; 0 de los 109 guardados caen como basura. Harness `frontend/scripts/hintsHarness.ts`. |
| **Score / affinity** (`score.ts`, `affinity.ts`, `tempo.ts`, `crateIndex.ts`) | Sobre los 206 sugeridos AUC **0.456** (peor que el azar); sobre el pool de 1.954 AUC 0.424, p@30 = 1/30 | Sugeridos AUC **0.587**; pool AUC **0.660, p@30 = 7/30** (4,3× la tasa base). Obscurity penaliza mainstream con razón visible; curador → source quality; tempo con rango del oído (plegado 92% correcto); época por escena; affinity aprende por dato según provenance; Dexie v3 con `*sourceIds`/`*tags`, `seen` con contexto y **hit rate propio** (mostradas/guardadas). Harness `frontend/scripts/scoreBench.ts`. |
| **Vetas / UI** (`youtube.ts`, `useCrateStore.ts`, `ui/`) | Vetas = solo canales por API, tope 100 | Pegar playlist o canal ajeno y **cavarlo entero por tandas** con cursor = seen y "visto/total": cobertura 1.958/1.958 en el benchmark, 0 repetidos; la primera tanda de 240 trae 19,2% de guardados vs 5,5% de base (×3,5). AnalyzePanel muestra ventana/ambigüedad y **÷2/×2** con provenance `user/manual`; ResultCard muestra razones negativas y "~1,7k views". Harness `frontend/scripts/vetaBench.ts`. |
| **Docs** | Afirmaban "baja un fragmento", "< 1000 views", estado viejo | CLAUDE.md (estado, "el oído de Thomas, medido", requisitos), ROADMAP, SOURCES, ARCHITECTURE, ENTITY_MODEL (affinity por dato), READMEs, agentes. |

## Lo que quedó abierto (para la próxima sesión)

1. **YouTube bot-check en descargas.** Durante la noche YouTube empezó a responder *"Sign in to confirm
   you're not a bot"* a las descargas de audio desde esta IP (el listado flat sigue andando). El
   backend ya lo detecta (404 con detail, cooldown `CRATE_YOUTUBE_BLOCK_COOLDOWN_SEC`) y acepta
   cookies (`CRATE_YTDLP_COOKIES`, p.ej. exportadas del navegador). Si "Analizar audio" da ese
   error, es eso, no un bug.
2. **Tres cabos sueltos que la revisión encontró y no entraban en el área del que arreglaba:**
   `crateIndex.reject/remove` reescriben la fila y pierden `shown/skippedFor/tags` (las rechazadas
   no suman al hit rate); `setBpmManual` (÷2/×2) no actualiza `affinity.bpmBuckets`;
   `skippedSourceIds` no está cableado en `useCrateStore.search()/mine()`. Son chicos.
3. **Probar a mano en la app:** guardar → analizar → ÷2 y ver que el crate/affinity cambie;
   rechazar y ver `rechazadas` en el hit rate; importar las 5 playlists propias; minar un canal
   curador entero. Dexie no se probó contra IndexedDB real (no hay fake-indexeddb ni vitest).
4. **Fusion sigue flojo en octava (47% backend / 61% cliente):** swing y tresillos rompen la
   jerarquía ½/1/2 (errores 3:2, 3:4). Es el límite del método por evidencia; la corrección a mano
   es lo que lo va a mejorar.
5. **Rarity y richness no se calibraron:** el benchmark no tiene want/have ni créditos de Discogs
   (hace falta un snapshot de `videos.list` + cruce Discogs del pool, ~40 unidades de quota).
6. Commit y merge a `develop` cuando Thomas lo revise.

## Conclusiones (lo que pidió Thomas)

- **La joya no se anuncia en el título.** Lo que funcionó fue leer todo con varias miradas; la app
  ahora puede cavar una veta entera en vez de quedarse con 24 elegidos por título.
- **Su oído, medido:** 109/206 guardados (53%). La **obscuridad pesa más que el encaje canónico**
  (lo mainstream con millones de views no lo guarda aunque encaje); la **década es blanda si la
  escuela es la misma** (90–92 quiet storm: TOP); el **tempo es duro** (> ~115 BPM real: no);
  **redistribuye** entre listas (un "no encaja acá" no es rechazo). R&B fue el flojo (33%) porque
  el perfil que usé era más setentoso que su lista real.
- **Los canales curadores son la mejor pista de fuente:** 30% de lo guardado vino de 38 canales;
  un canal del que ya guardó ≥1 tema tiene 16,5% de probabilidad de guardado vs 3,3%.
- **El DSP se equivocaba hacia arriba 4 de cada 5 veces en baladas;** ahora devuelve evidencia y
  el cliente decide con el rango del oído (82%). Lo que falta lo arregla la corrección manual.

## Cómo seguir subiendo el hit rate

1. **Importar sus 5 playlists como Saved con colección** (ya existe `save` con tags y el cursor por
   seen): es el seed de affinity más fuerte y evita re-mostrar lo que ya tiene.
2. **Sugerir por colección, no en general:** SOUL, R&B, CITY POP y FUSION tienen era/tempo/textura
   propios; la affinity por playlist es el próximo salto (el error de R&B lo demuestra).
3. **Cerrar el loop en la app:** cada sesión mide mostradas/guardadas/rechazadas; usar eso (no un
   fixture congelado) para tocar pesos. El benchmark de hoy queda como piso.
4. **Vetas nuevas:** las "Samples Vol." están agotadas (el ranking cortó limpio: 0 guardados fuera
   de lo sugerido). Minar enteros los canales que más le dieron y pedirle 3–5 playlists ajenas más.
5. **Que él corrija la octava y rechace con motivo:** un "no" con razón enseña más que diez "sí".

Meta realista para la próxima tirada con el filtro nuevo: de 53% a 65–70%.
