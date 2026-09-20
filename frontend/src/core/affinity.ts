/**
 * Affinity — el "oído" del usuario aprendido de su comportamiento.
 * Sin ML al principio: contadores de lo que guarda/analiza (y resta de lo que rechaza).
 * Ver docs/CRATE_SCORE.md
 *
 * Regla que manda (ver docs/ENTITY_MODEL.md): se aprende POR DATO según su
 * provenance, no por track. El canal del video es un hecho de la fuente y se
 * aprende siempre; el año solo con una pista dura (℗ del Topic, link a Discogs,
 * huella); el BPM solo si salió del audio (analizado o plegado) o lo corrigió el
 * usuario; géneros, sello y país solo de un disco de Discogs que matcheó
 * fuerte (`catalogMatch` ≥ 0.85 o link directo: `confirmed` solo no alcanza,
 * porque un Topic confirma la obra y no el disco elegido). Medido sobre
 * playlists reales: un título suelto como "Rainy Day" matchea Reggae/Ska, y
 * aprender de eso envenena el modelo. Y medido el 19-sep: 57% identificado /
 * 23% confirmado, así que aprender solo de lo confirmado dejaba a las vetas
 * (Oleg Tsoy, 42 temas en sus listas) sin aparecer nunca.
 */
import type { EnrichedTrack, MusicEntity, SourceItem } from './entities'
import type { Provenanced } from './provenance'
import { DEFAULT_TEMPO_PRIOR, type TempoRange } from './tempo'
import { canalDe, TEMAS_DE_RUIDO_PERSONAL, type Canal } from './canales'

export type Counter = Record<string, number>

/** Prefijo de las razones que BAJAN el score (el score lo re-exporta; la UI las pinta distinto). */
export const NEGATIVA = '↓ '

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
  /**
   * Canales de los que venís guardando (clave `${channelId}|${uploader}`).
   * Marca las VETAS: canales que ya demostraron tener tu material y que
   * conviene minar enteros. Entra al score solo como calidad de FUENTE
   * (`sourceQualityScore`), nunca como obscuridad de la obra.
   */
  channels: Counter
  /**
   * Tus colecciones (el nombre de la playlist importada o el tag con que
   * guardaste). Se cuentan pero no puntúan: estar en la misma playlist no es
   * gusto, es taxonomía tuya.
   */
  tags: Counter
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
    channels: {},
    tags: {},
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
  if (bpm == null || !(bpm > 0)) return undefined
  const lo = Math.floor(bpm / 10) * 10
  return `${lo}-${lo + 10}`
}

/** Nombres que no son un artista: placeholders nuestros y los canales Topic genéricos. */
const NO_ES_ARTISTA = new Set(['unknown', 'buscando…', 'release', 'various', 'various artists', 'varios'])

const artistKey = (artist?: string): string | undefined => {
  const k = artist?.trim().toLowerCase()
  return k && !NO_ES_ARTISTA.has(k) ? k : undefined
}

/** Clave del canal en `affinity.channels`. Sin channelId (flat de playlist) va por uploader. */
export function channelKey(s: Pick<SourceItem, 'channelId' | 'uploader'> | undefined): string | undefined {
  if (!s) return undefined
  if (!s.channelId && !s.uploader) return undefined
  return `${s.channelId ?? ''}|${s.uploader ?? ''}`
}

/** ¿El año viene de una pista dura (℗ del Topic, link a Discogs, huella)? */
function anioDuro(t: EnrichedTrack): boolean {
  const by = t.entity.identifiedBy
  return by === 'catalog_link' || by === 'topic_channel' || by === 'acoustid'
}

/** ¿El BPM salió del audio (analizado o plegado) o lo corrigió el usuario? */
function bpmProvDeAudio(b: Provenanced<number> | undefined): boolean {
  if (!b || b.confidence < 0.4) return false
  if (b.source === 'user' && b.method === 'manual') return true
  return b.source === 'audio_analysis' && (b.method === 'analyzed' || b.method === 'inferred')
}

const bpmDeAudio = (t: EnrichedTrack): boolean => bpmProvDeAudio(t.bpm)

/**
 * ¿Los géneros/estilos/sello/país de la entidad salen de un disco de Discogs
 * que matcheó FUERTE? `confirmed` no alcanza: un Topic confirma la obra por el
 * bloque ℗, pero el release de Discogs de donde vienen los géneros pudo
 * elegirse con 0.62 de similitud ("Rainy Day" → Reggae/Ska). Con link directo
 * es un id; con `catalogMatch` se exige ≥ 0.85; sin ese dato (pipeline viejo)
 * vale lo confirmado salvo el Topic, que es justo el caso envenenado.
 */
function catalogoFuerte(e: MusicEntity): boolean {
  if (!e.confirmed) return false
  if (e.identifiedBy === 'catalog_link') return true
  if (e.catalogMatch != null) return e.catalogMatch >= 0.85
  return e.identifiedBy !== 'topic_channel'
}

/**
 * Aprende de un track. weight = +1 al guardar/analizar, -1 al rechazar.
 * Inmutable: devuelve una copia nueva.
 *
 * (a) Hechos de la fuente: siempre. (b) Pistas duras: año y artista solo con
 * identificación fuerte. (c) Interpretaciones de catálogo: solo si la obra está
 * confirmada. Un track sin confirmar enseña poco, pero enseña.
 */
export function learn(prev: Affinity, track: EnrichedTrack, weight = 1): Affinity {
  const a = structuredClone(prev)
  const e = track.entity

  // (a) hechos de la fuente
  const yt = track.sources.find((s) => s.kind === 'youtube') ?? track.sources[0]
  bump(a.channels, channelKey(yt), weight)
  ;(track.tags ?? []).forEach((tag) => bump(a.tags, tag, weight))
  if (bpmDeAudio(track)) bump(a.bpmBuckets, bpmBucket(track.bpm?.value), weight)

  // (b) pistas duras
  if (e.year && (e.confirmed || anioDuro(track))) bump(a.eras, decadeOf(e.year), weight)
  if (e.confirmed || anioDuro(track)) bump(a.artists, artistKey(e.artist), weight)

  // (c) interpretaciones de catálogo: solo de un disco que matcheó fuerte
  const catalogo = catalogoFuerte(e)
  if (catalogo) {
    e.genres.forEach((g) => bump(a.genres, g, weight))
    e.styles.forEach((s) => bump(a.styles, s, weight))
    bump(a.countries, e.country, weight)
    bump(a.labels, e.label, weight)
    ;(track.mood?.value.feels ?? []).forEach((f) => bump(a.feels, f, weight))
    ;(track.mood?.value.textures ?? []).forEach((t) => bump(a.textures, t, weight))
  } else if (e.label && e.discogsId == null && anioDuro(track)) {
    // sin disco de Discogs, el sello vino del ℗ del Topic: pista dura, no interpretación
    bump(a.labels, e.label, weight)
  }
  const instr = track.instruments
  if (instr && (instr.method === 'analyzed' || (catalogo && instr.method === 'catalog'))) {
    instr.value.forEach((i) => bump(a.instruments, i, weight))
  }

  a.total += weight
  return a
}

/**
 * Aprende SOLO el tempo, cuando cambia el BPM de una ficha que YA está en el
 * crate: re-análisis, o corrección a mano (÷2 / ×2). Descuenta el bucket viejo
 * si había salido del audio o de la mano del usuario (o sea, si `learn` lo
 * había contado) y suma el nuevo. Sin esto el prior de tempo solo podía
 * achicarse: `tasteTempoRange` aprendía de valores ya plegados al prior y
 * nunca veía el 150 real que el usuario corrigió.
 */
export function learnBpmOnly(
  prev: Affinity,
  oldBpm: Provenanced<number> | undefined,
  newBpm: Provenanced<number> | undefined,
  weight = 1,
): Affinity {
  const a = structuredClone(prev)
  if (bpmProvDeAudio(oldBpm)) bump(a.bpmBuckets, bpmBucket(oldBpm?.value), -weight)
  if (bpmProvDeAudio(newBpm)) bump(a.bpmBuckets, bpmBucket(newBpm?.value), weight)
  return a
}

function rel(rec: Counter, key: string | undefined): number | null {
  if (!key) return null
  const values = Object.values(rec)
  if (values.length === 0) return null
  const max = Math.max(1, ...values)
  return (rec[key] ?? 0) / max
}

/** Cuántas veces guardaste a este artista (0 si nunca). */
export function timesSaved(a: Affinity, artist?: string): number {
  const k = artistKey(artist)
  if (!k) return 0
  return Math.max(0, a.artists[k] ?? a.artists[artist ?? ''] ?? 0)
}

/**
 * Cuántos temas guardaste de este canal. Con channelId busca exacto; una
 * playlist importada sin channelId (flat) queda contada por uploader.
 */
export function timesFromChannel(
  a: Affinity,
  s: Pick<SourceItem, 'channelId' | 'uploader'> | undefined,
): number {
  if (!s) return 0
  const exact = channelKey(s)
  if (exact && a.channels[exact] != null) return a.channels[exact]
  let n = 0
  for (const [k, v] of Object.entries(a.channels)) {
    const [id, up] = k.split('|')
    if ((s.channelId && id === s.channelId) || (!s.channelId && s.uploader && up === s.uploader)) n += v
  }
  return n
}

/** El canal en la lista personal (`core/canales.ts`): curador o ruido, si está. */
export function canalDeTrack(t: EnrichedTrack): Canal | undefined {
  const s = t.sources.find((x) => x.kind === 'youtube') ?? t.sources[0]
  return s ? canalDe(s.channelId, s.uploader) : undefined
}

/**
 * Peso de la década en tu crate, suavizado con las vecinas: 1991 hereda parte
 * de los 80s (guardó quiet storm 90–92 "TOP"). null si no hay historial.
 */
export function eraWeight(a: Affinity, year?: number): number | null {
  const d = year ? Math.floor(year / 10) * 10 : undefined
  if (!d || Object.keys(a.eras).length === 0) return null
  const propia = rel(a.eras, `${d}s`) ?? 0
  const vecina = Math.max(rel(a.eras, `${d - 10}s`) ?? 0, rel(a.eras, `${d + 10}s`) ?? 0)
  return Math.max(0, Math.min(1, 0.7 * propia + 0.3 * vecina))
}

/** Cuántos temas con BPM de audio enseñaron el rango. */
const MIN_TEMAS_PARA_PRIOR = 30

/**
 * El rango de tempo del oído: p5–p95 de `bpmBuckets` cuando hay ≥30 temas con
 * BPM de audio; hasta entonces, el default medido (58–115). Es el prior que usa
 * `tempo.ts::foldBpm` para elegir la octava: un dato del usuario, no de CRATE.
 */
export function tasteTempoRange(a: Affinity): TempoRange {
  const buckets = Object.entries(a.bpmBuckets)
    .map(([k, n]) => ({ lo: Number(k.split('-')[0]), n }))
    .filter((b) => Number.isFinite(b.lo) && b.n > 0)
    .sort((x, y) => x.lo - y.lo)
  const total = buckets.reduce((s, b) => s + b.n, 0)
  if (total < MIN_TEMAS_PARA_PRIOR) return DEFAULT_TEMPO_PRIOR
  let acum = 0
  let min = DEFAULT_TEMPO_PRIOR.min
  let max = DEFAULT_TEMPO_PRIOR.max
  let minListo = false
  for (const b of buckets) {
    acum += b.n
    if (!minListo && acum >= total * 0.05) {
      min = b.lo
      minListo = true
    }
    if (acum >= total * 0.95) {
      max = b.lo + 10
      break
    }
  }
  return { min, max }
}

/**
 * 0..1: cuánto pega el track con el crate aprendido. 0.5 si no hay historial.
 *
 * - El artista repetido SUMA (1 guardado → 0.33, 3 → 1.0). Se probó acotarlo
 *   y penalizarlo ("no es un hallazgo") y el ranking empeoró: Thomas guarda más
 *   de artistas que ya tiene. El score lo dice igual, para que él decida.
 * - La época NO entra: la puntúa `historicalRelevance` (época de la escena o
 *   tu década), para no contarla dos veces.
 * - Ruido personal (canal con rol 'ruido' o del que ya rechazaste) tira abajo
 *   con razón: es gusto tuyo, no basura universal.
 */
export function affinityScore(track: EnrichedTrack, a: Affinity, reasons?: string[]): number {
  const e = track.entity
  const src = track.sources.find((s) => s.kind === 'youtube') ?? track.sources[0]

  // Ruido PERSONAL (no basura universal): canal marcado como ruido, título
  // de OST de juego/anime o vaporwave, o canal del que ya rechazaste varios.
  const canal = canalDeTrack(track)
  const rechazadosDelCanal = -Math.min(0, timesFromChannel(a, src))
  const tituloRuido = TEMAS_DE_RUIDO_PERSONAL.test(src?.title ?? '')
  if (canal?.rol === 'ruido' || tituloRuido || rechazadosDelCanal >= 2) {
    reasons?.push(
      canal?.rol === 'ruido'
        ? `${NEGATIVA}${src?.uploader ?? 'este canal'}: ruido para tu oído (${canal.nota ?? 'lo marcaste como ruido'})`
        : tituloRuido
          ? `${NEGATIVA}OST de juego/anime o vaporwave: ruido para tu oído`
          : `${NEGATIVA}ya rechazaste ${rechazadosDelCanal} de ${src?.uploader ?? 'este canal'}`,
    )
    return 0.1
  }

  if (a.total <= 0) return 0.5
  // el artista no se normaliza por el máximo como el resto: con 3 temas
  // guardados de alguien ya es "tuyo" (medido: 71% de guardado contra 47%)
  const artista =
    artistKey(e.artist) == null || Object.keys(a.artists).length === 0
      ? null
      : Math.min(1, timesSaved(a, e.artist) / 3)
  const signals: Array<number | null> = [
    ...e.genres.map((g) => rel(a.genres, g)),
    ...e.styles.map((s) => rel(a.styles, s)),
    ...(track.instruments?.value ?? []).map((i) => rel(a.instruments, i)),
    rel(a.countries, e.country),
    rel(a.labels, e.label),
    artista,
    rel(a.bpmBuckets, bpmBucket(track.bpm?.value)),
  ]
  const present = signals.filter((x): x is number => x != null)
  if (present.length === 0) return 0.5
  const avg = present.reduce((s, x) => s + x, 0) / present.length
  return Math.max(0, Math.min(1, avg))
}
