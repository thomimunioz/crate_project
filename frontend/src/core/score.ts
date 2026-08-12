/**
 * CRATE Score — "¿qué tan probable es que esto sea una joya que NO encontraste?"
 * Separa rarity ≠ obscurity ≠ discovery value. Siempre explicable (reasons → "Why this?").
 * Ver docs/CRATE_SCORE.md
 */
import type { EnrichedTrack, SearchQuery } from './entities'
import type { Affinity } from './affinity'
import { affinityScore } from './affinity'

export interface ScoreComponents {
  filterMatch: number
  rarity: number
  obscurity: number
  metadataRichness: number
  sourceQuality: number
  historicalRelevance: number
  personalAffinity: number
}

export interface CrateScore {
  /** 0..100 */
  total: number
  components: ScoreComponents
  /** motivos legibles para el "Why this?" */
  reasons: string[]
}

/**
 * Pesos recalibrados con datos reales, no a ojo.
 *
 * Dos cosas cambiaron desde los valores iniciales y mueven la fórmula:
 *
 * 1. **La rareza dejó de ser un hueco.** Con el cruce contra catálogo al 72%,
 *    el 68% de los tracks trae want/have de Discogs. Antes ese componente
 *    devolvía el 0.3 neutro casi siempre; ahora discrimina de verdad, así que
 *    sube.
 * 2. **La obscuridad sigue siendo un eje, aunque el descubrimiento ya filtre.**
 *    Bajarla fue un error que corrigió la medición: con obscurity en 0.12, una
 *    búsqueda de MPB brasileño metía segundo a Sergio Mendes & Brasil '66 con
 *    39.062 views. Es correcto para la query y está confirmado, pero es
 *    exactamente lo que el usuario YA conoce. El fan-out baja la mediana a ~400
 *    views, pero adentro del resultado siguen conviviendo 429 y 39.062: ahí
 *    la obscuridad es lo único que los separa. Vuelve a 0.16.
 *
 * Rarity ≠ obscurity sigue valiendo: una obra rara de catálogo es otra cosa
 * que un upload que nadie miró. Ver docs/CRATE_SCORE.md.
 */
export const DEFAULT_WEIGHTS: ScoreComponents = {
  filterMatch: 0.24,
  rarity: 0.2,
  obscurity: 0.16,
  metadataRichness: 0.08,
  sourceQuality: 0.07,
  historicalRelevance: 0.08,
  personalAffinity: 0.17,
}

// épocas dulces para la estética del usuario (soul/jazz/city pop/MPB/library)
const SWEET_SPOTS: Array<[number, number]> = [
  [1968, 1979],
  [1980, 1986],
]

const clamp01 = (x: number): number => Math.max(0, Math.min(1, x))

function rarityScore(t: EnrichedTrack, reasons: string[]): number {
  const { discogsWant, discogsHave } = t.rarity
  if (discogsWant == null || discogsHave == null) return 0.3 // sin datos: neutral-bajo
  const ratio = discogsWant / Math.max(discogsHave, 1)
  const s = clamp01(Math.log10(1 + ratio) / 2) // ratio ~100 → ~1
  if (s > 0.6) reasons.push(`${discogsWant} wants / ${discogsHave} haves en Discogs (rareza alta)`)
  return s
}

function obscurityScore(t: EnrichedTrack, reasons: string[]): number {
  const views = t.rarity.youtubeViews
  if (views == null) return 0.4
  const ageDays = t.rarity.uploadAgeDays ?? 3650
  // descontar uploads nuevos: todavía no tuvieron chance de acumular views
  const ageFactor = clamp01(ageDays / 365)
  const raw = clamp01(1 - Math.log10(Math.max(views, 10)) / 6) // 10→~0.83, 1M→~0
  const s = clamp01(raw * (0.5 + 0.5 * ageFactor))
  if (views < 1000 && ageFactor > 0.5) reasons.push(`solo ${views.toLocaleString()} views en YouTube`)
  return s
}

/** De dónde salió la identificación, en castellano, para el "Why this?". */
const COMO_SE_IDENTIFICO: Record<string, string> = {
  catalog_link: 'el uploader linkeó el disco en Discogs',
  topic_channel: 'canal oficial del sello (metadata del distribuidor)',
  acoustid: 'identificado por huella acústica (no por el título)',
}

function richnessScore(t: EnrichedTrack): number {
  const e = t.entity
  let n = 0
  if (e.credits.length) n++
  if (e.year) n++
  if (e.label) n++
  if (e.genres.length || e.styles.length) n++
  if (e.confirmed) n++
  return clamp01(n / 5)
}

function sourceQualityScore(t: EnrichedTrack): number {
  const s = t.sources[0]
  if (!s) return 0.3
  let q = t.entity.confirmed ? 0.7 : 0.45
  const d = s.durationSec ?? 0
  if (d > 0 && d < 30) q -= 0.2 // muy corto: sospechoso
  if (d > 1800) q -= 0.3 // >30min: probable mix/álbum entero, no un track
  return clamp01(q)
}

function historicalRelevanceScore(t: EnrichedTrack, reasons: string[]): number {
  const y = t.entity.year
  if (!y) return 0.4
  for (const [a, b] of SWEET_SPOTS) {
    if (y >= a && y <= b) {
      reasons.push(`sweet spot ${a}–${b}`)
      return 0.9
    }
  }
  return 0.5
}

function filterMatchScore(t: EnrichedTrack, q: SearchQuery, reasons: string[]): number {
  let checks = 0
  let hits = 0
  const e = t.entity
  const tags = e.genres.concat(e.styles).map((x) => x.toLowerCase())
  const haveInstr = (t.instruments?.value ?? []).map((x) => x.toLowerCase())

  if (q.genres?.length) {
    checks++
    if (q.genres.some((g) => tags.some((tag) => tag.includes(g.toLowerCase())))) hits++
  }
  if (q.instruments?.length) {
    checks++
    const matched = q.instruments.filter((i) => haveInstr.includes(i.toLowerCase()))
    if (matched.length) {
      hits++
      reasons.push(`${matched.join(' + ')} (instrumentos que buscás)`)
    }
  }
  if (q.year) {
    checks++
    if (e.year && e.year >= q.year[0] && e.year <= q.year[1]) hits++
  }
  if (q.bpm && t.bpm) {
    checks++
    if (t.bpm.value >= q.bpm[0] && t.bpm.value <= q.bpm[1]) hits++
  }
  if (q.key && t.key) {
    checks++
    if (t.key.value.toLowerCase().startsWith(q.key.toLowerCase())) hits++
  }

  // Mood: los controles ya lo mandaban en la query y el score lo ignoraba.
  // Cuenta a medias porque es metadata inferida, no confirmada: pedir "dusty"
  // y que un disco no lo tenga no dice tanto como que no tenga el instrumento.
  const feels = t.mood?.value.feels ?? []
  const textures = t.mood?.value.textures ?? []
  if (q.feels?.length) {
    checks++
    const matched = q.feels.filter((f) => feels.includes(f))
    if (matched.length) {
      hits += 0.5 + 0.5 * (matched.length / q.feels.length)
      reasons.push(`${matched.join(' + ')} (el mood que pediste)`)
    }
  }
  if (q.textures?.length) {
    checks++
    const matched = q.textures.filter((x) => textures.includes(x))
    if (matched.length) hits += 0.5 + 0.5 * (matched.length / q.textures.length)
  }

  if (checks === 0) return 0.6 // sin filtros duros: no penalizar
  return clamp01(hits / checks)
}

/**
 * Cuánto sabemos REALMENTE de la obra, 0.55..1.
 *
 * Sin esto, un upload del que no sabemos nada puntúa como joya solo por tener
 * un año en el título y pocas views: medido, "Engelbert Humperdinck B9 -
 * Wand'rin' Star" con 20 views entraba cuarto en una búsqueda de MPB brasileño,
 * sin sello, sin géneros y sin cruce contra catálogo.
 *
 * El sweet spot y la obscuridad son señales sobre una OBRA. Si no sabemos qué
 * obra es, no podemos afirmarlas con la misma fuerza. Es la misma regla que rige
 * todo CRATE: no mezclar lo confirmado con lo inferido.
 */
function certeza(t: EnrichedTrack): number {
  const e = t.entity
  if (e.confirmed) return 1
  const señales = [
    e.discogsId != null,
    e.recordingMbid != null,
    e.genres.length > 0 || e.styles.length > 0,
    e.label != null,
    e.credits.length > 0,
  ].filter(Boolean).length
  return 0.55 + 0.09 * señales
}

export function computeCrateScore(
  track: EnrichedTrack,
  query: SearchQuery,
  affinity: Affinity,
  weights: ScoreComponents = DEFAULT_WEIGHTS,
): CrateScore {
  const reasons: string[] = []
  const components: ScoreComponents = {
    filterMatch: filterMatchScore(track, query, reasons),
    rarity: rarityScore(track, reasons),
    obscurity: obscurityScore(track, reasons),
    metadataRichness: richnessScore(track),
    sourceQuality: sourceQualityScore(track),
    historicalRelevance: historicalRelevanceScore(track, reasons),
    personalAffinity: affinityScore(track, affinity),
  }
  const comoSeIdentifico = track.entity.identifiedBy
    ? COMO_SE_IDENTIFICO[track.entity.identifiedBy]
    : undefined
  if (comoSeIdentifico) reasons.push(comoSeIdentifico)

  if (components.personalAffinity > 0.6) {
    reasons.push(`${Math.round(components.personalAffinity * 100)}% match con tu crate`)
  }

  let total = 0
  let wsum = 0
  for (const k of Object.keys(weights) as (keyof ScoreComponents)[]) {
    total += components[k] * weights[k]
    wsum += weights[k]
  }

  const seguridad = certeza(track)
  if (seguridad < 1) reasons.push('sin cruzar contra catálogo: el puntaje va descontado')

  return { total: Math.round((total / wsum) * seguridad * 100), components, reasons }
}

/** Etiqueta para la UI según el score. */
export function scoreLabel(total: number): string {
  if (total >= 85) return '🔥 Hidden Gem'
  if (total >= 70) return '✦ Strong dig'
  if (total >= 55) return 'Worth a listen'
  return 'Deep cut'
}
