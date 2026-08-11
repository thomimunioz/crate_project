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


## 🟢 Implementado en backend (último recurso)

### AcoustID (huella acústica)
- **Aporte:** identifica la grabación **sin depender del texto** → devuelve MBID de grabación,
  artista y título. Es la única salida para lo que el cruce por texto no puede resolver:
  títulos en kanji y títulos sueltos sin artista (ver medición abajo).
- **Dónde:** server-side, `POST /identify` (`backend/app/fingerprint.py`). No pasa por el proxy:
  la key nunca sale del backend.
- **Costo:** gratis, 3 req/seg por key. Necesita `fpcalc` (Chromaprint) instalado.
- **Gotcha:** se huella un **fragmento** (120s desde el arranque), no el track entero, así que la
  confidence se descuenta por cobertura. Si arrancás el fragmento en el medio del tema, la huella
  deja de alinear con la de referencia. La cobertura de AcoustID depende de que alguien haya
  subido esa grabación: para prensados oscuros puede no haber nada.

## Opcional / tangencial

### Freesound
- Texturas/one-shots CC **con BPM/key ya analizados** (API gratis). Útil, pero **no son
  "discos de otra gente"** → fuera del núcleo, queda como fuente opcional.

## Medición real del cruce (agosto 2026, 80 temas de las playlists del usuario)

El cruce contra catálogo es **el** cuello de botella de calidad: sin él no hay
créditos, ni sello, ni want/have, o sea no hay CRATE Score ni affinity.

| estrategia | cruce | nota |
|---|---|---|
| Discogs `q=` libre + Levenshtein concatenado | **14%** | el estado original |
| Discogs `artist=` + `track=` estructurado | 26% | la mayoría son **falsos positivos** |
| MusicBrainz `recording:` | 33% | y los matches son correctos |
| **MusicBrainz identifica → Discogs enriquece** | **57%** | el pipeline actual |

Resultado del pipeline actual sobre los mismos 80 temas: **57% identificados,
44% con want/have, 31% con créditos por instrumento, 23% confirmados.** Que
"confirmado" sea bastante menor que "identificado" es a propósito: se identifica
más de lo que se afirma. Tarda 134s para 80 temas (1 llamada a MB + hasta 2 a
Discogs por tema, serializadas por rate limit) → **el render progresivo pasa a
ser obligatorio, no cosmético.**

Puntos flojos que quedan: `dark` 13% y `japanese city pop` 38% de identificación
con 0% de créditos. Son títulos sin artista o en kanji; MusicBrainz no los tiene
y el fallback por texto libre contra Discogs tampoco alcanza. **Para esos dos casos
el texto ya no da más: es el laburo de la huella acústica** (`POST /identify`), que
identifica la grabación sin leer el título. Falta medir cuánto sube el 57% con ella.

Tres causas encontradas, ya corregida la primera:

1. `splitArtistTitle` limpiaba antes de partir, y el limpiador se come `~ | /`
   como decorado → 51% de los temas quedaban sin artista. **Corregido.**
2. **Discogs busca releases (álbumes); los títulos de YouTube son tracks.**
   Buscar "Breve vita, non felice" contra títulos de disco no puede funcionar.
   Con `artist=`+`track=`, cuando Discogs no encuentra el track igual devuelve
   otros discos del artista → matchea cualquier cosa del mismo autor.
3. Levenshtein sobre `artista + título` concatenados lo domina el largo del
   nombre del artista: "Ennio Morricone - Debora" matcheó "Ennio Morricone -
   Amore" con 0.82 siendo otro tema.

**Conclusión: MusicBrainz debería ser el primer salto** (identifica la grabación,
que es el nivel correcto) y Discogs el segundo (enriquece ese release con
créditos y rareza). MB además resuelve títulos sin artista, que con Discogs son
imposibles. Contras: MB tiene **0% en city pop japonés** —justo el punto débil—,
donde Discogs sí tiene catálogo. Son complementarias, no sustitutas.

## La señal que YouTube ya nos da (y que no leíamos)

El `snippet` de `videos.list` trae **descripción, tags y canal** en la misma llamada
de 1 unidad que ya hacemos para las views. Ahí adentro hay identificación exacta:

- **Canales `- Topic`**: los genera YouTube desde el feed de las discográficas, con
  formato fijo → `<tema> · <artista>`, disco, y `℗ <año> <sello>`. Es un dato de
  catálogo disfrazado de descripción.
- **Links directos a Discogs/MusicBrainz**: muchos diggers pegan el release. Es un
  id, no una interpretación: se va derecho al release sin buscar ni comparar.
- **Tags**: el artista en romaji, kanji y katakana a la vez. Es lo que abre la
  puerta al catálogo japonés, donde el match por texto fracasa.

Medido sobre playlists completas del usuario: 38% de los temas de city pop japonés
vienen de un canal `- Topic` y 58% traen tags, **justo la playlist donde el cruce
por texto daba 0% de créditos.** El problema nunca fue falta de datos.

Implementación: [`frontend/src/core/ytHints.ts`](../frontend/src/core/ytHints.ts).
Cuando hay pista dura, la entidad se marca `confirmed` sin pasar por el fuzzy.

## Vetas: minar canales en vez de buscar

`search.list` cuesta **100 unidades**; los uploads de un canal cuestan **1 cada 50
videos**. Por tema es ~200 veces más barato.

Los uploads de un canal viven en una playlist implícita cuyo id es el del canal con
`UC` cambiado por `UU`. Un canal del que ya guardaste varios temas es un **curador
humano que hizo el digging antes que vos**, y su catálogo entero está sobre la
tesis. La affinity cuenta de qué canales guardás (`affinity.channels`) y a partir
de dos temas ese canal se ofrece como veta para minar entero.

No entra al score —un hallazgo nuevo puede venir de cualquier lado—, es un vector
de descubrimiento, no una señal de calidad.

## Gotchas transversales (leer sí o sí)

1. **CORS:** algunas fuentes y todo scraping se bloquean desde el navegador → proxy fino en
   backend (allowlist) desde el Tier 0. Ver `backend/app/proxy.py`.
2. **Extracción de audio de YouTube:** no se puede en el cliente → `yt-dlp` baja un fragmento
   temporal en el backend, se analiza y se descarta. Ver `backend/app/dsp.py`.
3. **Fuzzy matching:** los títulos de YouTube son sucios → normalización + Levenshtein antes
   de cruzar con Discogs. Ver `frontend/src/core/fuzzy.ts`.
