/**
 * Affinity — el "oído" del usuario aprendido de su comportamiento.
 * Sin ML al principio: contadores de lo que guarda/analiza (y resta de lo que rechaza).
 * Ver docs/CRATE_SCORE.md
 */
import type { EnrichedTrack } from './entities'

export type Counter = Record<string, number>

export interface Affinity {
  genres: Counter
  styles: Counter
  instruments: Counter
  eras: Counter
  countries: Counter
  labels: Counter
  artists: Counter
  feels: Counter
  textures: Counter
  bpmBuckets: Counter
  total: number
}

export function emptyAffinity(): Affinity {
  return {
    genres: {},
    styles: {},
    instruments: {},
    eras: {},
    countries: {},
    labels: {},
    artists: {},
    feels: {},
    textures: {},
    bpmBuckets: {},
    total: 0,
  }
}

function bump(rec: Counter, key: string | undefined, weight: number): void {
  if (!key) return
  rec[key] = (rec[key] ?? 0) + weight
}

function decadeOf(year?: number): string | undefined {
  return year ? `${Math.floor(year / 10) * 10}s` : undefined
}

function bpmBucket(bpm?: number): string | undefined {
  if (bpm == null) return undefined
  const lo = Math.floor(bpm / 10) * 10
  return `${lo}-${lo + 10}`
}

/**
 * Aprende de un track. weight = +1 al guardar/analizar, -1 al rechazar.
 * Inmutable: devuelve una copia nueva. Los tracks sin confirmar no enseñan.
 */
export function learn(prev: Affinity, track: EnrichedTrack, weight = 1): Affinity {
  // Solo se aprende de entidades confirmadas. Un cruce dudoso trae género y
  // sello del disco equivocado: medido sobre playlists reales, títulos sueltos
  // como "Rainy Day" matchean con Reggae/Ska o Heavy Metal. Aprender de eso
  // envenena el modelo de gusto, que es justo lo que hace personal al producto.
  if (!track.entity.confirmed) return prev

  const a = structuredClone(prev)
  const e = track.entity
  e.genres.forEach((g) => bump(a.genres, g, weight))
  e.styles.forEach((s) => bump(a.styles, s, weight))
  ;(track.instruments?.value ?? []).forEach((i) => bump(a.instruments, i, weight))
  ;(track.mood?.value.feels ?? []).forEach((f) => bump(a.feels, f, weight))
  ;(track.mood?.value.textures ?? []).forEach((t) => bump(a.textures, t, weight))
  bump(a.eras, decadeOf(e.year), weight)
  bump(a.countries, e.country, weight)
  bump(a.labels, e.label, weight)
  bump(a.artists, e.artist, weight)
  bump(a.bpmBuckets, bpmBucket(track.bpm?.value), weight)
  a.total += weight
  return a
}

function rel(rec: Counter, key: string | undefined): number | null {
  if (!key) return null
  const values = Object.values(rec)
  if (values.length === 0) return null
  const max = Math.max(1, ...values)
  return (rec[key] ?? 0) / max
}

/** 0..1: cuánto pega el track con el crate aprendido. 0.5 si no hay historial. */
export function affinityScore(track: EnrichedTrack, a: Affinity): number {
  if (a.total <= 0) return 0.5
  const e = track.entity
  const signals: Array<number | null> = [
    ...e.genres.map((g) => rel(a.genres, g)),
    ...e.styles.map((s) => rel(a.styles, s)),
    ...(track.instruments?.value ?? []).map((i) => rel(a.instruments, i)),
    rel(a.eras, decadeOf(e.year)),
    rel(a.countries, e.country),
    rel(a.labels, e.label),
    rel(a.artists, e.artist),
    rel(a.bpmBuckets, bpmBucket(track.bpm?.value)),
  ]
  const present = signals.filter((x): x is number => x != null)
  if (present.length === 0) return 0.5
  const avg = present.reduce((s, x) => s + x, 0) / present.length
  return Math.max(0, Math.min(1, avg))
}
