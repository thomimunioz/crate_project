# Entity Model & Provenance

CRATE es **dueño de la entidad musical canónica**. Las fuentes descubren y enriquecen, pero
la verdad vive en la entidad normalizada de CRATE. Esto evita el error clásico de asumir
`YouTube video = track = release`, que se rompe rapidísimo.

## El pipeline de identidad

```
SOURCE ITEM            un video de YouTube / item de Internet Archive / (futuro) SC, BC, web
      │                puede ser: 1 tema, un álbum entero, un rip de vinilo, un DJ mix,
      │                un live, una compilación, un upload "FULL ALBUM 1974"...
      ▼
CANDIDATE              parseo del title/description/tags → artista?, título?, año?, bpm?, key?
      │                (todo tentativo, con baja/media confidence) + `hints` del snippet:
      │                pista dura (link a Discogs, Topic con ℗/Released on), convenciones de
      │                título del canal digger (`titleHints`, parsed 0.6–0.7), uploader como
      │                artista (`artistFromChannel`, parsed ≤ 0.6), créditos por rol
      ▼
MUSIC ENTITY           la entidad canónica de CRATE: Recording / Track dentro de un Release
      │                se resuelve cruzando contra Discogs + MusicBrainz (fuzzy match)
      ▼
ENRICHED TRACK         entidad + metadata provenienciada (year, genre, style, credits,
                       rarity, bpm/key/mood/instruments) + score + estado
```

Ver los tipos en [`frontend/src/core/entities.ts`](../frontend/src/core/entities.ts).

## Normalización (la parte difícil)

YouTube te da títulos como `T. Yamashita ~ Sparkle (1982) [Vinyl Rip] HQ`. Discogs tiene
`Tatsuro Yamashita – Sparkle`. El matcher tiene que ser tolerante:

0. **Pistas duras primero** (`core/ytHints.ts`) — un link a Discogs en la descripción o un
   canal `- Topic` es un id o un dato de catálogo, no una interpretación: confirma sin fuzzy.
   Ojo con el `℗` del Topic: en reediciones digitales es el año del fonograma, no de la obra
   (℗ 2007 de un LP de 1985). Se lee `Released on:` y `℗ Originally released`; con brecha,
   recopilatorio o sello reeditor → `reissue: true` y el año lo decide el catálogo.
1. **Split artista / título** — por separador (` - `, ` – `, ` ~ `, ` | `, ` / `, ` -- `, guion
   con espacio de un solo lado, 2+ espacios, `／`). Se parte **antes** de limpiar: el limpiador
   borra `~ | /` como decorado y se lleva puesto el separador, dejando la mitad de los temas
   sin artista. Los caracteres invisibles que pega Discogs (LRM/ZWSP) se sacan antes.
2. **Limpieza** de cada mitad — `[Vinyl Rip]`, `HQ`, `(1982)`, `FULL ALBUM`, `official`, `lyrics`.
   Las **convenciones de título de canales digger** (`[US] Soul, Jazz (1980)`, `- 1982 - Japan`,
   `Álbum (1983) - A3 - Título`…) se parsean a `hints.titleHints` con `method: 'parsed'`; NO se
   escriben en `entity.country/genres/year`, que son campos de catálogo. Mezclarlos inflaría
   `metadataRichness` y `certeza` como si la obra estuviera cruzada.
3. **Identificación en MusicBrainz** — busca a nivel **grabación**, que es el nivel en el que
   vive un título de YouTube. Devuelve artista canónico, disco y año. Exige score ≥ 85 y, si
   el título traía artista, que coincida.
4. **Enriquecimiento en Discogs** — con el disco ya identificado, búsqueda estructurada
   `artist=` + `release_title=` para traer créditos por instrumento, sello, país y want/have.
   El match se puntúa **campo contra campo**; concatenar deja que el largo del nombre del
   artista domine la distancia.

Si MusicBrainz no identifica, se cae al cruce por texto libre contra Discogs. Si Discogs no
encuentra el disco pero MB identificó, igual queda una entidad usable.

Implementación: [`frontend/src/core/fuzzy.ts`](../frontend/src/core/fuzzy.ts) y
[`frontend/src/pipeline/index.ts`](../frontend/src/pipeline/index.ts).

> **La identidad es del track, no del disco.** El `crateId` usa el MBID de grabación, que es
> track-level. Usar el id de release de Discogs colapsa todos los cortes de un mismo álbum
> en una sola clave.

> **Confirmar lo decide quien identificó.** Si MusicBrainz identificó, manda su confianza:
> que Discogs después encuentre ese disco solo prueba que los dos catálogos coinciden, no que
> la identificación haya sido buena. Y lo no confirmado **no le enseña metadata de catálogo
> a la affinity** (ver la regla por dato, abajo).

> Regla: si el fuzzy match no supera el umbral, la entidad queda como "sin confirmar" y su
> metadata de catálogo NO se marca como `confirmed`. Mejor honesto que inventado.

## Provenance: cada dato sabe de dónde viene

Ningún dato entra "pelado". Todo valor sensible se envuelve en `Provenanced<T>`:

```ts
interface Provenanced<T> {
  value: T
  source: 'youtube_title' | 'youtube_tags' | 'youtube_description' | 'discogs' | 'musicbrainz'
        | 'archive' | 'audio_analysis' | 'acoustid' | 'inferred' | 'user'
  method: 'parsed' | 'catalog' | 'analyzed' | 'fingerprint' | 'inferred' | 'manual'
  confidence: number   // 0..1
  updatedAt: string    // ISO
}
```

Y en la UI se muestra la diferencia, nunca se colapsa:

```
84 BPM · del título              (confirmado del texto)
86 BPM · analizado 94%           (DSP, alta confianza)
76 BPM · plegado a tu rango      (audio_analysis/inferred: el DSP leyó 152, el prior eligió la mitad)
76 BPM · corregido a mano        (user/manual: ÷2/×2 en el AnalyzePanel)
soulful · inferido 62%           (deducido de género + tags)
```

**El BPM plegado no se disfraza de analizado.** El backend devuelve `value` + `alternatives`
+ `ambiguous` sin prior de gusto; el cliente (`core/tempo.ts::foldBpm`) elige la octava con
el rango del usuario. Si pliega, la ficha lleva `audio_analysis` / `inferred` con razón
(confidence × 0,9) y el crudo, las alternativas, la ventana y el prior usado quedan en la
tabla `analyses` de Dexie. Si el DSP ya cae en el rango, va `analyzed` tal cual.

Implementación: [`frontend/src/core/provenance.ts`](../frontend/src/core/provenance.ts).

## Affinity: aprende por DATO, según su provenance

La affinity (`core/affinity.ts`) no aprende "del track": aprende **de cada dato según de
dónde salió**. Medido: un título suelto como "Rainy Day" matchea Reggae/Ska en Discogs, y
aprender de eso envenena el modelo; pero aprender solo de lo confirmado (23% del pool)
dejaba a las vetas (Oleg Tsoy, 42 temas en sus listas) sin aparecer nunca.

| dato | se aprende cuando |
|---|---|
| canal (`channels`) | **siempre**: es un hecho de la fuente, no una interpretación |
| tags / colección | siempre (se cuentan; no puntúan) |
| BPM (`bpmBuckets`) | solo `audio_analysis` (`analyzed` o `inferred`) o `user/manual` |
| década (`eras`) | solo con pista dura: ℗ del Topic, link a Discogs, huella, o confirmado |
| artista | confirmado o con pista dura (`catalog_link`, `topic_channel`, `acoustid`) |
| instrumentos | analizados por audio, o de créditos de catálogo confirmado |
| géneros, estilos, sello, país, feels/texturas | **solo si la obra está confirmada** |

Lo negativo también es dato: un canal con rol `ruido` en `core/canales.ts`, un título de OST
de anime/videojuego o vaporwave, o un canal del que ya rechazaste 2+ → affinity 0,1 con razón.
Es gusto de ESTE usuario, no basura universal (eso vive en `esBasura`).

El prior de tempo sale de acá (`tasteTempoRange`: p5–p95 de `bpmBuckets` con 30+ temas,
default 58–115) y se recalibra con cada corrección manual. Detalle: `docs/CRATE_SCORE.md`.

## Estados del track (Seen / Saved / Analyzed / Rejected)

```
SEEN       lo viste pasar (historial / cache temporal)         → NO es tu crate
SAVED      lo guardaste                                        → parte del crate
ANALYZED   le corriste DSP                                     → parte del crate
REJECTED   dijiste "no me interesa"                            → se oculta a futuro
```

- **Índice principal (tu crate) = Saved + Analyzed.**
- `Seen` habilita la feature clave de F1: **"no me muestres lo que ya vi"**, y desde el
  crate-index v3 guarda el **contexto** en que se mostró (`queryText`, `shownAt`, `origen`
  veta/búsqueda, `sessionId`): con eso `hitRate()` / `hitRatePorQuery()` calculan
  mostradas/guardadas/rechazadas sin scripts. Una veta ajena entra entera como `seen`.
- `Rejected` alimenta negativamente la affinity y filtra ruido. Es global: "no me interesa".
- **"No para esta búsqueda" ≠ rechazo** (`skipFor(track, queryText)`): Thomas redistribuye
  entre colecciones, así que un "no encaja en 80s" no resta affinity; solo deja de mostrarse en
  esa query. `save(track, { tags })` guarda con la colección para que lo guardado desde la app
  lleve la misma taxonomía que lo importado.
- `raw` de YouTube nunca se persiste; los ids de fuente van en el índice `*sourceIds`.

Modelo persistido en IndexedDB (Dexie): [`frontend/src/db/crateIndex.ts`](../frontend/src/db/crateIndex.ts).
