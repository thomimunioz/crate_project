# CRATE — Spec de producto (v0.2)

> v0.1 fue el spec inicial (artifact). v0.2 integra las revisiones de ChatGPT y Gemini:
> entity model, provenance con confidence, estados seen/saved/analyzed/rejected, CRATE Score
> explicable, taxonomía de mood, y los gotchas técnicos (CORS, yt-dlp, fuzzy matching).

## 1. Visión

Un buscador de **crate-digging** que rastrea la web abierta para encontrar **discos reales de
otra gente** —joyas ocultas— y **construye tu propio índice mientras buscás**. Para beatmakers
de hiphop con oído a soul, jazz fusion, city pop, MPB, quiet storm, library, 80s.

No compite con Splice/Tracklib/Loopcloud. Ataca otro problema:
**"sé que hay música increíble ahí afuera, pero no sé dónde carajo encontrarla."**

## 2. La obsesión

El éxito se mide con una pregunta: **¿encontré algo que no hubiera encontrado buscando normal?**
El mayor riesgo no es técnico, es la **calidad de resultados**. Todo se subordina a eso.

La métrica es el **hit rate** (guardados / sugeridos) sobre lo que el usuario escucha de
verdad, no las views. Baseline a mano, 19-sep-2026: 109/206 = 53%
(`docs/benchmarks/2026-09-19-digging-a-mano/`). Cada cambio de discovery, hints, score o DSP
se mide contra ese benchmark antes y después (ver `docs/ROADMAP.md`, "Cómo se mide").

## 3. Alcance de la interacción

- **Descubrir + preview.** Nada de descargar/capturar audio dentro de la app.
- Herramienta **personal** (keys propias), arquitectura lista para multiusuario a futuro.
- **Web + PWA** (desktop y mobile).

## 4. Dos capas

- **Capa 1 (browser, metadata-first):** meta-search + text-mining + cruce Discogs/MusicBrainz.
- **Capa 2 (opt-in, backend):** botón "Analizar audio" → yt-dlp (descarga temporal completa,
  se recorta y se borra) + DSP → BPM/key con evidencia (alternativas, ambigüedad); la octava la
  elige el cliente con el rango del usuario.

Un backend **liviano** existe desde el día 1 (CORS proxy + discovery sin quota con yt-dlp +
DSP), pero no es el cerebro: devuelve evidencia, nunca gusto.

## 5. Modelo de datos (resumen — detalle en ENTITY_MODEL.md)

`Source Item → Candidate → Music Entity (Recording/Release/Track) → Enriched Track`.
CRATE es dueño de la entidad canónica. Cada dato lleva `{ value, source, method, confidence, updatedAt }`.
Estados: `seen / saved / analyzed / rejected`; el crate real = `saved + analyzed`.

## 6. CRATE Score (detalle en CRATE_SCORE.md)

Responde "¿probabilidad de que sea una joya que no encontraste?". Componentes: filterMatch,
rarity, obscurity, metadataRichness, sourceQuality, historicalRelevance, personalAffinity.
Separa **rarity ≠ obscurity ≠ discovery value**. Siempre explicable vía **"Why this?"**.

## 7. Filtros y taxonomía (detalle en TAXONOMY.md)

- BPM (rango), Key/modo, año/era, género/estilo (taxonomía Discogs), país, sello.
- **Instrumentos** — de créditos de Discogs (¡sin tocar audio!) o de DSP.
- **Mood** — ejes cerrados: Energy 1–5 · Feel · Texture. Nada de campos libres.
- Diseñado para traducir **lenguaje natural → filtros** a futuro (no en F1).

## 8. Personalización (affinity)

CRATE aprende de tu comportamiento (lo que guardás/analizás/rechazás): géneros, instrumentos,
rangos de BPM, épocas, países, sellos, artistas, moods. Al principio sin ML: contadores.
Eso convierte al crate-index en **tu** crate, no en un cache genérico.

## 9. Fuentes (detalle en SOURCES.md)

- **F1:** YouTube (API + yt-dlp sin quota: búsqueda y playlists/canales ajenos como vetas) ·
  Discogs · MusicBrainz · Internet Archive · AcoustID (huella acústica, opt-in por ficha).
- **F2:** Spotify (referencia), web search, Bandcamp, Freesound.
- **F3:** Soulseek, SoundCloud.

## 10. Identidad visual

Mundo del **crate-digging** + **vinilo japonés de los 70**: crates, etiquetas, fichas, stickers,
sellos, timestamps, discos, polvo. Texturas vintage, tonos cálidos algo desvanecidos, ligero
grano cinematográfico. Motivo de **consola de sampler / pantalla LCD ámbar** para los datos
(BPM/key). Lejos de las interfaces clínicas y aburridas del software moderno.

Tipografía: mono para datos/readouts (LCD), sans/serif con carácter para lectura.

## 11. Nombre

**CRATE.** Explica la filosofía al instante para alguien que hace beats y abre todo un mundo de
branding: *Your crate · Dig deeper · The internet is the crate · Find what nobody else found.*

## 12. Roadmap (detalle en ROADMAP.md)

F1 el núcleo (discovery real + score + crate personal), F2 ampliar red + NL search, F3 lo pesado.

## 13. Riesgos

1. **Calidad de resultados** (el grande): mitigar con score obsesivo + benchmark real
   (hit rate, AUC) que se corre antes y después de cada cambio.
2. **Quota de YouTube:** ya no es el cuello de botella (yt-dlp busca y lista a costo 0);
   `videos.list` se pide solo para la tanda que se enriquece. Cachear igual.
3. **Fragilidad de scraping (Bandcamp) / APIs cerradas (SoundCloud):** aislar tras el proxy, degradar con gracia.
4. **Fuzzy match impreciso:** umbral + marcar entidades no confirmadas en vez de inventar.
5. **Legal/ToS:** discovery + preview; el DSP hace una descarga temporal que se recorta, se
   analiza y se borra; nunca se sirve ni se redistribuye audio.
6. **yt-dlp / YouTube se rompen cada pocos meses** (403, desafío JS, runtime): mantener
   `yt-dlp` + `yt-dlp-ejs` al día, exigir node 22+ / deno 2.3+, y un `GET /health` que diga qué
   falta en vez de fallar en silencio.
7. **Sobreajustar al gusto de un usuario:** el oído de Thomas es dato con fecha y n (affinity,
   `canales.ts`, prior de tempo), no regla del backend; tiene que poder cambiar por persona.
