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
      │                (todo tentativo, con baja/media confidence)
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

1. **Limpieza** — sacar ruido: `[Vinyl Rip]`, `HQ`, `(1982)`, `FULL ALBUM`, `official`,
   `lyrics`, corchetes/paréntesis con basura, emojis, separadores raros (`~`, `|`, `//`).
2. **Split artista / título** — heurísticas por separador (` - `, ` – `, ` ~ `).
3. **Match** — Levenshtein / similitud sobre `artist + title` contra los resultados de Discogs;
   se queda con el mejor por encima de un umbral, y **guarda el score de match como confidence**.

Implementación: [`frontend/src/core/fuzzy.ts`](../frontend/src/core/fuzzy.ts).

> Regla: si el fuzzy match no supera el umbral, la entidad queda como "sin confirmar" y su
> metadata de catálogo NO se marca como `confirmed`. Mejor honesto que inventado.

## Provenance: cada dato sabe de dónde viene

Ningún dato entra "pelado". Todo valor sensible se envuelve en `Provenanced<T>`:

```ts
interface Provenanced<T> {
  value: T
  source: 'youtube_title' | 'youtube_tags' | 'discogs' | 'musicbrainz'
        | 'archive' | 'audio_analysis' | 'inferred' | 'user'
  method: 'parsed' | 'catalog' | 'analyzed' | 'inferred' | 'manual'
  confidence: number   // 0..1
  updatedAt: string    // ISO
}
```

Y en la UI se muestra la diferencia, nunca se colapsa:

```
84 BPM · del título        (confirmado del texto)
86 BPM · analizado 94%     (DSP, alta confianza)
soulful · inferido 62%     (deducido de género + tags)
```

Implementación: [`frontend/src/core/provenance.ts`](../frontend/src/core/provenance.ts).

## Estados del track (Seen / Saved / Analyzed / Rejected)

```
SEEN       lo viste pasar (historial / cache temporal)         → NO es tu crate
SAVED      lo guardaste                                        → parte del crate
ANALYZED   le corriste DSP                                     → parte del crate
REJECTED   dijiste "no me interesa"                            → se oculta a futuro
```

- **Índice principal (tu crate) = Saved + Analyzed.**
- `Seen` habilita la feature clave de F1: **"no me muestres lo que ya vi"**.
- `Rejected` alimenta negativamente la affinity y filtra ruido.

Modelo persistido en IndexedDB (Dexie): [`frontend/src/db/crateIndex.ts`](../frontend/src/db/crateIndex.ts).
