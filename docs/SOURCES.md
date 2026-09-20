# Fuentes — mapa, quotas, CORS y gotchas

Mapa honesto de dónde salen las joyas y qué cuesta integrar cada una.
Clients: [`frontend/src/sources/`](../frontend/src/sources/).

## 🟢 Núcleo sólido (F1)

### YouTube — dos caminos: yt-dlp lista, la API enriquece
- **Aporte:** el corazón del discovery. Discos, rips, edits, uploads oscuros de 200 views, y
  las playlists de otros diggers (curación gratis).
- **Regla (20-sep-2026):** **yt-dlp lista, `videos.list` enriquece.** Buscar y listar no gasta
  quota; la descripción/fecha/tags (que el flat NO trae) se piden a la API solo para la tanda
  que se va a enriquecer, a 1 unidad cada 50 ids.

| operación | vía | costo | dónde |
|---|---|---|---|
| búsqueda por texto | yt-dlp `ytsearch` | **0** | `GET /discover` (`backend/app/discover.py`) |
| búsqueda por texto (fallback si el backend no está) | API `search.list` | **100** | `sources/youtube.ts::buscarIdsConQuota` |
| listar una playlist ajena (id o URL) | yt-dlp flat | **0** | `GET /discover/playlist?url=&offset=&limit=` |
| listar los uploads de un canal (UC…, @handle, URL) | yt-dlp flat sobre la playlist `UU…` | **0** | `GET /discover/channel?url=&offset=&limit=` |
| stats + snippet (descripción, tags, fecha, views exactas) | API `videos.list` | **1 / 50 ids** | `sources/youtube.ts::fetchStats` |
| playlist propia para importar | yt-dlp flat + API `videos.list` (fallback `playlistItems` si el backend no está) | 0 + 1 / 50 | `sources/youtube.ts::fetchPlaylist` |

- Con el fan-out de 3 lanes, una búsqueda pasó de 303 unidades a 3. Una playlist de 200 se
  lista en ~1,5 s; un canal de 1.845 uploads en 10 tandas de 200 (o 4 de 500) de 2–7 s cada
  una (medido con `@Musicforemptyrooms`; Oleg Tsoy tiene 5.351). Tope 500 por tanda, default
  200; el cursor es `next_offset` (null = terminó) y `total` sale de `playlist_count`.
- **Lo que el flat trae:** id, título, uploader, channel_id, duración, views **redondeadas**
  (`views_approx: true` → la UI dice "~1,7k"), `playlist_index`, thumbnail, `unavailable`
  para borrados/privados (se marcan, no se filtran: decide el cliente).
- **Lo que el flat NO trae:** descripción, `upload_date`, tags, likes. Sin `videos.list`, los
  hints del snippet (℗, link a Discogs, tags en kanji) quedan vacíos y el 47% de canales
  `- Topic` cae al fuzzy.
- **CORS:** la API anda desde el browser con API key; yt-dlp corre en el backend.
- **Quota de la API:** 10.000 unidades/día. Sigue importando para `videos.list`, pero ya no
  es el cuello de botella.
- **Gotcha CLI:** `yt-dlp --print` con `\t` imprime un backslash-t literal; el backend usa la API
  de Python con `extract_flat`. Las entries flat de una playlist NO traen `playlist_index`
  (se lee de `requested_entries` del padre) y las del tab de un canal NO traen
  `uploader`/`channel_id` (se propagan del padre; por eso se lista la `UU…`).
- **Gotcha:** no da BPM/key. Sale de tags/título o del botón Analizar. El audio no se toca
  desde el cliente (protecciones) → para DSP, el backend usa `yt-dlp` (requisitos abajo).

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
- **Gotcha:** se huella un **recorte** (0–120 s desde el arranque), no el track entero, así que la
  confidence se descuenta por cobertura. Si arrancás el recorte en el medio del tema, la huella
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
| MusicBrainz identifica → Discogs enriquece | 57% | |
| **+ pistas duras del snippet de YouTube** | **72%** | el pipeline actual |

Resultado del pipeline actual sobre 79 temas de las 10 playlists: **72%
identificados, 71% confirmados, 68% con want/have, 52% con créditos por
instrumento.** El 46% se identifica por pista dura, sin fuzzy.

Ojo con un detalle que parece raro: en algunas playlists **confirmado > identificado**.
Es correcto. "Identificado" cuenta los que tienen MBID o id de Discogs; una pista
dura de canal `- Topic` da artista, disco, año y sello desde el feed del sello sin
que exista match en catálogo. Sabemos qué es aunque no lo hayamos linkeado.

`japanese city pop` pasó de 38% identificado y 0% créditos a **75% / 25%**, con 63%
por pista dura: era la peor playlist y ahora está entre las mejores. La que queda
floja es `dark` (38%).

Lo que sigue sin identificar es exactamente lo que el texto no puede: títulos en
cirílico, títulos sueltos de una palabra, y rips sin descripción. **Ese es el
trabajo de la huella acústica**, no de más ajustes al matcher.

Tarda ~148s para 79 temas (1 llamada a MB + hasta 2 a Discogs por tema,
serializadas por rate limit) → por eso el render progresivo es obligatorio. **Para esos dos casos
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

### Lo que se aprendió leyendo 1.958 títulos a mano (19-sep-2026)

Medido con `cd frontend && npm run hints` sobre `docs/benchmarks/2026-09-19-digging-a-mano/`
(pool + 175 descripciones). Antes → después de reescribir los hints:

- Artista parseado sobre el pool: 39% → **52%**. Entre los no-Topic, 66% → 73% por título;
  sumando el **nombre del canal como artista** (`artistFromChannel`, `parsed`, confidence
  ≤ 0,6, solo cuando el título no tiene forma "Artista - Tema" y el canal no es digger), 90%.
- Topic con descripción: título correcto 0/78 → 78/78; álbum 0 → 65/78; créditos por rol
  ("Electric Piano: George Duke") 0 → 54/78; año de la OBRA 72/78.
- **Reediciones:** el `℗` de un canal Topic es el año del fonograma digital, no de la obra
  (℗ 2007 de un LP de 1985; "Complete Atlantic Recordings"; Numero Group). Se lee también
  `Released on:` y `℗ Originally released 1974`; si hay brecha ≥ 2 años, recopilatorio o
  sello reeditor, `reissue: true`, `year` queda vacío y decide MB/Discogs.
- **Convenciones de título de canales digger** (`parseTitleConventions`, 8 formas,
  `method: 'parsed'`, 0,6–0,7): `Artista - Título [US] Soul, Jazz (1980)` (Music for empty
  rooms) · `Artista - Título - 1982 - Japan` (ants kask, con posición A4) · `[Género] (1980 -
  País)` (Crackle Journey) · `(Library, 1980)` · `Artista - Álbum (1983) - A3 - Título` (My
  Vinyl Collection) · cadena de paréntesis (foreal) · bilingüe kanji/romaji · `Artista – Título
  (1975)`. Van en `hints.titleHints`, NO en `entity.country/genres/year` (campos de catálogo).
  El pipeline los consume en `normalize` (artista/título/año con prioridad hints > split >
  canal) y en el reintento de MusicBrainz con `artistAlias`/`titleAlias` (`enrichOne`).
- Separadores que rompían el split: ` -- `, guion con espacio de un solo lado, 2+ espacios,
  caracteres invisibles que pega Discogs (LRM/ZWSP), `／` full-width. "Jean-Claude" y "AC/DC"
  no se parten.
- `esBasura` sigue siendo universal (karaoke, sped up, tutorial, "full album" > 20 min sin
  forma "Artista - Tema"): **0 de los 109 guardados caen como basura**. Lo personal (OST de
  anime, vaporwave) NO va ahí: va en `core/canales.ts` y lo aplica la affinity.

Lo que falta para medir de verdad: un snapshot de `videos.list` de los 1.958 ids (~40
unidades) con las descripciones multilínea reales; hoy solo 175, planas.

## Vetas: canales y playlists de otros diggers

Una veta es un pool que **otro digger ya curó**: los uploads de un canal o una playlist
ajena. Es la forma más barata y más rendidora de encontrar material: el 19-sep-2026, 10
playlists ajenas ("Samples Vol. 00–09", canal DIGGING, 1.958 temas) dieron 206 sugerencias
y **109 guardadas (53%; 58% en la entrega 80s)**. Ver
`docs/benchmarks/2026-09-19-digging-a-mano/`.

- **Listar no cuesta nada:** `GET /discover/playlist` y `GET /discover/channel` (yt-dlp flat,
  0 quota, de a 200). Los uploads de un canal viven en la playlist `UU…` (el `UC` del id
  cambiado por `UU`); listarla en vez del tab `/videos` da `uploader`/`channel_id` por entry y
  el total. El cliente las cablea en `pipeline/index.ts::abrirVeta` → `listarMas` →
  `proximaTanda` → `cavarVeta`, y `useCrateStore.mine/mineMore` lleva `mining.visto/total`
  (el `Transporte` de `App.tsx` lo muestra y "seguir cavando" pide la próxima tanda).
- **Se lee TODO.** La joya no se anuncia en el título; elegir 24 por lo que dice el título es
  grep. La cobertura tiene que ser total por tandas, con `seen` como cursor y solo descarte de
  basura dura. Medido: dentro de una veta el portero por título no separa nada (AUC 0,52).
- **Entra como `seen`, nunca como `saved`.** A diferencia del import de una playlist propia,
  una ajena no es tu curaduría: guardarla entera ensucia el crate y la affinity.
- **Dónde salen las vetas:** de la affinity (`affinity.channels`, canales de los que ya
  guardaste ≥ 2), de la lista de curadores validados (`core/canales.ts`, abajo), y pegando
  cualquier URL, @handle o id de playlist/canal en `Vetas.tsx` (`parseVetaRef`).

**Qué entra al score y qué no.** Minar una veta no suma puntos. Pero **provenir de un canal
curador** (validado a mano o del que ya guardaste) sí es señal, y entra **solo a
`sourceQuality`** con razón visible ("subido por Soultwinz, curador que ya te dio 3 temas"):
dice de quién lo subió, no de cuán rara o escondida está la obra. **Nunca a obscurity**
(CLAUDE.md: rarity ≠ obscurity ≠ discovery value). Medido en el pool: de un canal del que ya
guardó, guarda 16–22%; del resto, 3%.

### Canales curadores validados a mano (19-sep-2026, un solo usuario)

Viven como datos en [`frontend/src/core/canales.ts`](../frontend/src/core/canales.ts)
(`CANALES`, `canalDe(channelId, uploader)`, `esCurador`), mantenidos por **crate-scout** junto
a `scenes.ts`. Son provenance `manual` con fecha: en multiusuario pasan a ser por persona.
Pedir siempre el `channelId`, no el nombre (BigPeter86 / BigPeter1027 / BigPeter1086 son la
misma familia y cambian de nombre).

Curadores de soul/jazz raro (38 con rol `curador`): Rare Samples & Songs Oleg Tsoy,
TheRAREGROOVEMAN, Soultwinz, `si`, Sample Soul 70, Music for empty rooms, André Navarro II,
Krem Soulz, BigPeter86/1027/1086 Real Music Channel, ants kask, Portal Records, Vinyle
Archéologie, Athens of The North, Family Old School Music, skeenery, Casen Fike, Inspiration in
sound, Late Night Quiet Storm Ballad Music Channel, mikeejaylovessoul, DJSoul832, Neglected
Trax, Brazilian Nuggets, JazzManDean, Obscure Samples, foreal, Boca Do Sol, 曲, Five Special
Records, lexingtunes, AUGUSTA GA 60'S and Other States Plus, SOULKATA, Terrestrial Funk, Winta
Groove, Crackle Journey, Antonio Pérez (curated by), My Vinyl Collection. Sample Soul 70,
Portal Records, Family Old School Music y My Vinyl Collection están sin `channelId` (no
aparecieron en el pool): resolverlos al verlos.

Ruido **para este usuario** (10 con rol `ruido`: 9 canales de OST/covers de anime y
videojuegos —Naruto, Cardcaptor, Gundam, Persona, Half-Life— y 1 de karaoke) más el
vocabulario de `TEMAS_DE_RUIDO_PERSONAL` (títulos de videojuegos/anime, vaporwave, future
funk). Lo aplica la affinity (0,1 con razón); no es basura universal. Karaoke, tutorial y
"full album" > 20 min sin forma "Artista - Tema" sí lo son, y los corta `esBasura`.

## AcoustID (huella acústica) — el desempate cuando el texto no puede

Chromaprint calcula una huella del audio y AcoustID la resuelve a un MBID de
grabación. **No depende del texto**, así que es lo único que identifica títulos
en kanji o títulos sueltos sin artista. Gratis para uso no comercial.

Backend: `backend/app/fingerprint.py` + `POST /identify`. Comparte la descarga con el
análisis de BPM/key (`dsp.download_audio`): `POST /analyze` con `identify: true` baja una
vez y hace dos recortes (la ventana para BPM/key, 0–120 s para la huella). La key vive en el
backend (`CRATE_ACOUSTID_KEY`) y nunca sale al browser. Necesita `fpcalc` (Chromaprint):
si falta, responde 503 con el motivo y `/analyze` sigue andando.

> **Gotcha que costó caro:** AcoustID separa los valores del parámetro `meta` por
> **espacio**. Con `recordings+releasegroups` o `recordings,releasegroups` devuelve
> el match con su score pero **sin nada de metadata**, y parece falta de cobertura.
> Encima, en un POST form-encoded el `+` viaja como `%2B`, o sea un plus literal.
> Verificado contra la API: solo `"recordings releasegroups"` trae las grabaciones.

Ejemplo real: 山下達郎 — SPARKLE, cuyo título en kanji el cruce por texto no puede
leer, sale identificado por sonido con score 0.958, su MBID y los discos donde
aparece. La confianza pondera por cobertura: un match sobre un recorte corto
nunca sale como seguro.

## Gotchas transversales (leer sí o sí)

1. **CORS:** algunas fuentes y todo scraping se bloquean desde el navegador → proxy fino en
   backend (allowlist) desde el Tier 0. Ver `backend/app/proxy.py`.
2. **Extracción de audio de YouTube:** no se puede en el cliente → en el backend, `yt-dlp`
   hace una **descarga temporal completa** de `bestaudio` (~4 MB, ~2 s), `ffmpeg` recorta la
   ventana a WAV mono 22050, Librosa analiza, y todo se borra en `finally`. Nunca se sirve.
   Ver `backend/app/dsp.py`. El recorte por `download_ranges` (lo que se usaba antes) delega en
   ffmpeg y YouTube responde 403: por eso se baja entero.
3. **yt-dlp se rompe cada pocos meses** cuando YouTube cambia. Requisitos reales (20-sep-2026):
   `yt-dlp >= 2026.08.19` + `yt-dlp-ejs`, y un runtime JS (**node 22+** o **deno 2.3+**; sin
   yt-dlp-ejs, node no resuelve el desafío). Sin runtime: "Requested format is not available".
   Los 403 esporádicos se reintentan con espera 2/5/8 s (`ytdl.with_retry`); los "video no
   disponible" no. `backend/app/ytdl.py` centraliza todo y `GET /health` lo cuenta. Listar y
   buscar (flat, `ytsearch`) **no** necesitan runtime JS ni API key.
4. **Fuzzy matching:** los títulos de YouTube son sucios → normalización + Levenshtein antes
   de cruzar con Discogs. Ver `frontend/src/core/fuzzy.ts`. Cualquier cambio en `cleanTitle`
   se mide con `npm run hints` (dedupe por `claveDeObra` y cobertura de artista).
