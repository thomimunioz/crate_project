# Fuentes — mapa, quotas, CORS y gotchas

Mapa honesto de dónde salen las joyas y qué cuesta integrar cada una.
Clients: [`frontend/src/sources/`](../frontend/src/sources/).

## 🟢 Núcleo sólido (F1)

### YouTube (Data API v3)
- **Aporte:** el corazón del discovery. Discos, rips, edits, uploads oscuros de 200 views.
- **CORS:** OK desde el browser con API key.
- **Quota:** 10.000 unidades/día gratis; `search.list` = **100 unidades** → ~100 búsquedas/día.
  `videos.list` = 1 unidad (barato para traer stats/details). **Cuidar la quota**: cachear,
  paginar con criterio, no quemar búsquedas.
- **Gotcha:** no da BPM/key. Sale de tags/título o del botón Analizar. El audio no se toca
  desde el cliente (protecciones) → para DSP, el backend usa `yt-dlp`.

### Discogs
- **Aporte:** el catálogo de discos del mundo. Género, estilo, año, sello, país,
  **créditos por instrumento** y rareza (`community.want` / `community.have`).
- **CORS:** puede fallar desde el browser → **usar el proxy** (`/api/proxy`) por las dudas.
- **Rate limit:** ~60 req/min autenticado. Requiere token + `User-Agent` propio.
- **Gotcha:** sin audio. Te dice qué cazar; el audio se escucha en YouTube.

### MusicBrainz
- **Aporte:** enciclopedia abierta; IDs canónicos (MBID) para cruzar/desambiguar entidades.
- **Rate limit:** **1 req/seg** (estricto) + `User-Agent` obligatorio → conviene pasar por el proxy con throttling.
- **Gotcha:** metadata pura, sin audio. Es el pegamento entre fuentes.

### Internet Archive (archive.org)
- **Aporte:** discos viejos digitalizados (78s, soul, jazz, library), legal y descargable.
- **CORS:** `advancedsearch.php` es amigable (JSON).
- **Gotcha:** metadata/calidad despareja; hay que filtrar. API abierta y gratis.

## 🟡 Con asteriscos (F2)

### Spotify
- **Aporte:** descubrir por playlist/género/año, referencia de vibe.
- **Gotcha grande:** las apps **nuevas** ya **no** acceden a *audio-features* (tempo/key/energy/
  valence) desde el **deprecado de nov-2024**, ni a recommendations/related. Y el audio va con
  DRM. Queda como **fuente de referencia**, no de metadata ni de audio. Confirmar al implementar.

### Búsqueda web general
- **Aporte:** "internet en general" — blogs, foros, uploads sueltos.
- **Gotcha:** necesita una API (Brave Search / SerpAPI) y filtrado fino. Vía backend.

### Bandcamp
- **Aporte:** soul/jazz/beat indie con la estética justa.
- **Gotcha:** sin API pública → scraping vía proxy backend (zona gris de ToS). Con cuidado.

### WhoSampled
- **Aporte:** digging inverso; además sirve para **penalizar lo ya-sampleado** en el score.
- **Gotcha:** API solo por partnership; scraping cuidadoso.

## 🔴 Pesados (F3)

### Soulseek
- **Aporte:** archivos rarísimos, el arma secreta P2P.
- **Gotcha:** P2P → backend **siempre prendido** conectado a la red (`aioslsk` / Nicotine+).
  File-sharing = zona gris. Fase 3.

### SoundCloud
- **Gotcha:** API prácticamente cerrada a apps nuevas hace años. Integración inestable.

### Fingerprinting (AcoustID / ACRCloud)
- **Aporte:** identificar un rip de YouTube y linkearlo al release real → cierra el fuzzy match.
- **Gotcha:** requiere calcular fingerprint del audio (chromaprint). Fase 3.

## Opcional / tangencial

### Freesound
- Texturas/one-shots CC **con BPM/key ya analizados** (API gratis). Útil, pero **no son
  "discos de otra gente"** → fuera del núcleo, queda como fuente opcional.

## Gotchas transversales (leer sí o sí)

1. **CORS:** algunas fuentes y todo scraping se bloquean desde el navegador → proxy fino en
   backend (allowlist) desde el Tier 0. Ver `backend/app/proxy.py`.
2. **Extracción de audio de YouTube:** no se puede en el cliente → `yt-dlp` baja un fragmento
   temporal en el backend, se analiza y se descarta. Ver `backend/app/dsp.py`.
3. **Fuzzy matching:** los títulos de YouTube son sucios → normalización + Levenshtein antes
   de cruzar con Discogs. Ver `frontend/src/core/fuzzy.ts`.
