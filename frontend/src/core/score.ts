/**
 * CRATE Score — "¿qué tan probable es que esto sea una joya que NO encontraste?"
 * Separa rarity ≠ obscurity ≠ discovery value. Siempre explicable (reasons → "Why this?"),
 * y eso incluye las penalizaciones: si el número baja, el usuario ve por qué.
 * Ver docs/CRATE_SCORE.md
 */
import type { EnrichedTrack, SearchQuery } from './entities'
import type { Affinity } from './affinity'
import {
  affinityScore,
  canalDeTrack,
  eraWeight,
  NEGATIVA,
  timesFromChannel,
  timesSaved,
} from './affinity'
import { ESCENAS, type Escena, type SceneId } from './scenes'
import { bpmWithinRange } from './tempo'

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
  /** motivos legibles para el "Why this?"; los que empiezan con `NEGATIVA` bajan el score */
  reasons: string[]
}

/**
 * De dónde viene el candidato y con qué plan se buscó. Todo opcional: sin
 * contexto el score se comporta como una búsqueda cruda sin escena.
 */
export interface ScoreContext {
  /** escenas del plan de digging: de acá salen la época y los nombres obvios */
  escenas?: SceneId[]
  /**
   * 'veta' = playlist/canal ajeno ya curado por otro digger; 'busqueda' = fan-out
   * crudo de YouTube. En una veta casi todo es sampleable y la obscuridad separa
   * menos: medido en el pool del 19-sep, lo guardado tiene mediana 25k views y
   * lo de <1k views se guardó al 2%. Ahí la obscuridad pesa la mitad.
   */
  origen?: 'veta' | 'busqueda'
}

/** Prefijo de las razones que BAJAN el score (vive en affinity.ts para no importar en círculo). */
export { NEGATIVA }
export const esRazonNegativa = (r: string): boolean => r.startsWith(NEGATIVA)

/**
 * Pesos recalibrados contra el oído real, no a ojo.
 *
 * Vara: `frontend/scripts/scoreBench.ts` sobre el benchmark del 19-sep-2026
 * (206 sugerencias de un pool curado, 109 guardadas; ver docs/benchmarks/).
 * Con la fórmula anterior el score ordenaba AL REVÉS (AUC 0.45 sobre lo que
 * escuchó; obscurity sola 0.33 sobre el pool): premiaba las pocas views y eso
 * en un pool curado es justo el ruido (OSTs, karaoke, mal titulados).
 *
 * Lo que mueve la fórmula hoy:
 * 1. **Obscurity ya no premia pocas views: castiga mainstream.** Meseta hasta
 *    100k y acantilado después. Lo que guardó tiene mediana 25k; lo que ignoró
 *    con millones de views encajaba perfecto (Whitney, Isleys, Patti Austin).
 * 2. **La fuente pesa.** Un canal del que ya guardaste varios temas es un curador
 *    humano: 66% de tasa de guardado contra 53% base. Va en sourceQuality, con
 *    razón, y nunca en obscurity (es calidad de la FUENTE, no rareza de la obra).
 * 3. **Rarity sigue alta** porque en una búsqueda real el 68% trae want/have de
 *    Discogs; en el benchmark no hay catálogo y queda plana, así que su peso no
 *    se pudo medir acá.
 *
 * Rarity ≠ obscurity sigue valiendo: una obra rara de catálogo es otra cosa
 * que un upload que nadie miró. Ver docs/CRATE_SCORE.md.
 */
export const DEFAULT_WEIGHTS: ScoreComponents = {
  filterMatch: 0.2,
  rarity: 0.18,
  obscurity: 0.1,
  metadataRichness: 0.06,
  sourceQuality: 0.22,
  historicalRelevance: 0.06,
  personalAffinity: 0.18,
}

/**
 * Épocas por defecto cuando no hay escena en el plan ni década aprendida.
 * Sin corte en 1986: el tier "1990–92" fue el de mejor tasa de guardado (50%)
 * en la entrega 80s del benchmark. La escuela manda, no la década.
 */
const SWEET_SPOTS: Array<[number, number]> = [
  [1968, 1979],
  [1980, 1992],
]

const clamp01 = (x: number): number => Math.max(0, Math.min(1, x))

function formatViews(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toLocaleString('es-AR', { maximumFractionDigits: 1 })}M`
  if (n >= 1_000) return `${(n / 1_000).toLocaleString('es-AR', { maximumFractionDigits: 1 })}k`
  return n.toLocaleString('es-AR')
}

function rarityScore(t: EnrichedTrack, reasons: string[]): number {
  const { discogsWant, discogsHave } = t.rarity
  if (discogsWant == null || discogsHave == null) return 0.3 // sin datos: neutral-bajo
  const ratio = discogsWant / Math.max(discogsHave, 1)
  const s = clamp01(Math.log10(1 + ratio) / 2) // ratio ~100 → ~1
  if (s > 0.6) reasons.push(`${discogsWant} wants / ${discogsHave} haves en Discogs (rareza alta)`)
  return s
}

/**
 * Curva de obscuridad en log10(views): meseta hasta 100k, bajada suave hasta
 * 300k, acantilado hasta 1M y cero en 10M. Medido en el pool del 19-sep: la
 * tasa de guardado es pareja de 5k a 300k (6–13%), cae a 4% arriba de 300k, y
 * abajo de 1k es 2% (ahí vive el ruido). Pocas views NO suman: solo dejan de
 * restar.
 */
const CURVA_VIEWS: Array<[number, number]> = [
  [5, 1.0], // 100k
  [5.48, 0.85], // 300k
  [6, 0.45], // 1M
  [7, 0], // 10M
]

function curvaViews(views: number): number {
  const x = Math.log10(Math.max(views, 1))
  if (x <= CURVA_VIEWS[0][0]) return 1
  for (let i = 1; i < CURVA_VIEWS.length; i++) {
    const [x0, y0] = CURVA_VIEWS[i - 1]
    const [x1, y1] = CURVA_VIEWS[i]
    if (x <= x1) return y0 + ((y1 - y0) * (x - x0)) / (x1 - x0)
  }
  return 0
}

function escenasDe(ctx: ScoreContext): Escena[] {
  if (!ctx.escenas?.length) return []
  return ESCENAS.filter((e) => ctx.escenas!.includes(e.id))
}

const escapeRe = (x: string): string => x.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** ¿El artista es un nombre sobreexpuesto de la escena (lo encontrás solo)? */
function nombreObvio(t: EnrichedTrack, escenas: Escena[]): string | undefined {
  const artista = t.entity.artist.toLowerCase()
  if (!artista || artista === 'unknown') return undefined
  for (const e of escenas) {
    // por palabra entera: "Anri" no tiene que pegar adentro de otro nombre
    const hit = e.obvios.find((o) =>
      new RegExp(`(^|[^\\p{L}\\p{N}])${escapeRe(o.toLowerCase())}([^\\p{L}\\p{N}]|$)`, 'u').test(
        artista,
      ),
    )
    if (hit) return hit
  }
  return undefined
}

/**
 * Obscurity = qué tan difícil es ENCONTRARLA. Ya no premia pocas views: lo
 * mainstream resta con razón visible, y "escondido de verdad" solo se afirma
 * sobre una obra identificada (un upload sin identificar con 200 views puede
 * ser cualquier cosa).
 */
function obscurityScore(t: EnrichedTrack, ctx: ScoreContext, reasons: string[]): number {
  const views = t.rarity.youtubeViews
  let s: number
  if (views == null) {
    s = 0.7 // sin views (Archive, etc.): ni mainstream ni escondido probado
  } else {
    const ageDays = t.rarity.uploadAgeDays ?? 3650
    // un upload de ayer todavía no acumuló views: no afirmar reach bajo con tanta fuerza
    const ageFactor = clamp01(ageDays / 365)
    s = clamp01(curvaViews(views) * (0.8 + 0.2 * ageFactor))
    // el flat de yt-dlp trae las views redondeadas: se dice "~1,7k", no "1.700"
    const v = `${t.sources[0]?.viewsApprox ? '~' : ''}${formatViews(views)} views`
    if (views >= 500_000) {
      reasons.push(`${NEGATIVA}${v}: esto ya lo conocés`)
    } else if (views < 5_000 && t.entity.confirmed && ageFactor > 0.5) {
      reasons.push(`${v} para un disco identificado: escondido de verdad`)
    }
  }

  const obvio = nombreObvio(t, escenasDe(ctx))
  if (obvio) {
    s *= 0.5
    reasons.push(`${NEGATIVA}${obvio}: nombre sobreexpuesto de la escena, lo encontrás solo`)
  }
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

/**
 * Calidad de la FUENTE: ¿es un buen rip de un tema, subido por alguien que
 * sabe? Acá entra el curador (canal del que ya guardaste, o de la lista
 * personal): es señal sobre quién lo subió, no sobre cuán rara es la obra.
 */
const mmss = (d: number): string => `${Math.floor(d / 60)}:${String(Math.round(d % 60)).padStart(2, '0')}`

function sourceQualityScore(t: EnrichedTrack, affinity: Affinity, reasons: string[]): number {
  const s = t.sources[0]
  if (!s) return 0.3
  let q = t.entity.confirmed ? 0.7 : 0.45

  // Duración: un tema sampleable dura entre 3 y 7 minutos. Medido en el pool
  // del 19-sep: de 253 items abajo de 3 min se guardó 1; de 25 arriba de
  // 10 min, ninguno; 83 de los 107 guardados duran entre 4 y 7 min.
  const d = s.durationSec ?? 0
  if (d > 0 && d < 30) {
    q -= 0.35
    reasons.push(`${NEGATIVA}dura ${d}s: demasiado corto para ser un tema`)
  } else if (d > 0 && d < 150) {
    q -= 0.15
    reasons.push(`${NEGATIVA}dura ${mmss(d)}: interludio o fragmento`)
  }
  if (d > 1800) {
    q -= 0.3
    reasons.push(`${NEGATIVA}dura ${Math.round(d / 60)} min: probable mix o álbum entero`)
  } else if (d > 600) {
    q -= 0.2
    reasons.push(`${NEGATIVA}dura ${mmss(d)}: probable suite, cara entera o mix`)
  }

  // Curador: quién lo subió. Medido en el pool: un canal del que ya guardaste
  // aunque sea 1 tema rinde 16% de guardado contra 3% del resto; con 2–3, 22%.
  // Un canal "Artista - Topic" no es un curador: es el distribuidor. Lo que
  // dice es "ya guardaste a este artista", y eso lo cuenta la affinity.
  const canal = canalDeTrack(t)
  const esTopic = /- Topic$/.test(s.uploader ?? '')
  const n = esTopic ? 0 : Math.max(0, timesFromChannel(affinity, s))
  const quien = s.uploader ?? canal?.nombre ?? 'este canal'
  if (canal?.rol === 'curador' && n >= 2) {
    q += 0.3
    reasons.push(`subido por ${quien}, curador que ya te dio ${n} temas`)
  } else if (canal?.rol === 'curador') {
    q += 0.2
    reasons.push(`subido por ${quien}, canal curador de la escena`)
  } else if (n >= 2) {
    q += 0.2
    reasons.push(`de ${quien}, de donde ya guardaste ${n}`)
  } else if (n >= 1) {
    q += 0.15
    reasons.push(`de ${quien}, de donde ya guardaste 1`)
  }
  return clamp01(q)
}

/**
 * Relevancia histórica = ¿cae en la época de la ESCENA que estás cavando?
 * Sin plan, cae a tu década (aprendida del crate) y, sin crate, a los sweet
 * spots por defecto. Es el único lugar donde puntúa la época: la affinity no
 * la cuenta de nuevo.
 */
function historicalRelevanceScore(
  t: EnrichedTrack,
  ctx: ScoreContext,
  affinity: Affinity,
  reasons: string[],
): number {
  const y = t.entity.year
  if (!y) return 0.4

  const escenas = escenasDe(ctx)
  if (escenas.length) {
    const adentro = escenas.find((e) => y >= e.epoca[0] && y <= e.epoca[1])
    if (adentro) {
      reasons.push(`${y} · época de ${adentro.nombre} (${adentro.epoca[0]}–${adentro.epoca[1]})`)
      return 0.9
    }
    const cerca = escenas.some((e) => y >= e.epoca[0] - 3 && y <= e.epoca[1] + 3)
    // fuera de época baja el score: se dice (toda señal negativa lleva razón)
    if (!cerca) {
      reasons.push(`${NEGATIVA}${y}: fuera de la época de ${escenas.map((e) => e.nombre).join(' / ')}`)
    }
    return cerca ? 0.65 : 0.35
  }

  const propia = affinity.total >= 20 ? eraWeight(affinity, y) : null
  if (propia != null) {
    if (propia >= 0.6) reasons.push(`${y} · década que venís guardando`)
    return 0.4 + 0.5 * propia
  }

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
    // el DSP se equivoca de octava hacia arriba (79% de los >115 eran el doble):
    // un 152 leído que es un 76 real no se descarta, cuenta a medias y se dice
    const v = t.bpm.value
    const como = bpmWithinRange(v, q.bpm[0], q.bpm[1])
    if (como === 'exact') hits++
    else if (como === 'octave') {
      hits += 0.5
      const otra = v > q.bpm[1] ? v / 2 : v * 2
      reasons.push(`${Math.round(v)} BPM leído; probablemente ${Math.round(otra)} (otra octava)`)
    }
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

/**
 * Artista repetido no es descubrimiento: otro tema del artista que más guardás
 * es lo primero que encontrarías solo. Se acota en la affinity y acá se DICE.
 *
 * Restar se probó y se revirtió: en el benchmark del 19-sep, Thomas guardó el
 * 71% de lo sugerido de artistas que ya tenía contra 47% de artistas nuevos, y
 * cada punto de penalidad bajaba el AUC (0.555 sin → 0.545 con 2%/tema → 0.535
 * con 5%/tema). La penalidad queda en 0 y la razón se muestra igual: el
 * usuario decide si eso es hallazgo o no. Volver a probar cuando el crate
 * tenga más de un día de historia.
 */
const PENALIDAD_ARTISTA_REPETIDO = 0
const MAX_PENALIDAD_ARTISTA = 0.06

export function computeCrateScore(
  track: EnrichedTrack,
  query: SearchQuery,
  affinity: Affinity,
  weights: ScoreComponents = DEFAULT_WEIGHTS,
  ctx: ScoreContext = {},
): CrateScore {
  const reasons: string[] = []
  const components: ScoreComponents = {
    filterMatch: filterMatchScore(track, query, reasons),
    rarity: rarityScore(track, reasons),
    obscurity: obscurityScore(track, ctx, reasons),
    metadataRichness: richnessScore(track),
    sourceQuality: sourceQualityScore(track, affinity, reasons),
    historicalRelevance: historicalRelevanceScore(track, ctx, affinity, reasons),
    personalAffinity: affinityScore(track, affinity, reasons),
  }
  const comoSeIdentifico = track.entity.identifiedBy
    ? COMO_SE_IDENTIFICO[track.entity.identifiedBy]
    : undefined
  if (comoSeIdentifico) reasons.push(comoSeIdentifico)

  if (components.personalAffinity > 0.6) {
    reasons.push(`${Math.round(components.personalAffinity * 100)}% match con tu crate`)
  }

  // el BPM plegado se dice con el crudo al lado, para que el usuario juzgue el pliegue
  const b = track.bpm
  if (b && b.source === 'audio_analysis' && b.method === 'inferred') {
    const crudo = track.bpmRaw
    reasons.push(
      crudo
        ? `${Math.round(b.value)} BPM · analizado ${Math.round(crudo.value)}, plegado a tu rango`
        : `${Math.round(b.value)} BPM · plegado a tu rango (el DSP leyó otra octava)`,
    )
  } else if (b && b.source === 'user' && b.method === 'manual' && track.bpmRaw) {
    reasons.push(`${Math.round(b.value)} BPM · corregido a mano (el DSP leyó ${Math.round(track.bpmRaw.value)})`)
  }

  // en una veta el pool ya viene curado: la obscuridad separa menos
  const pesos: ScoreComponents = { ...weights }
  if (ctx.origen === 'veta') pesos.obscurity = weights.obscurity * 0.5

  let total = 0
  let wsum = 0
  for (const k of Object.keys(pesos) as (keyof ScoreComponents)[]) {
    total += components[k] * pesos[k]
    wsum += pesos[k]
  }

  let factor = certeza(track)
  if (factor < 1) reasons.push(`${NEGATIVA}sin cruzar contra catálogo: el puntaje va descontado`)

  const repetido = timesSaved(affinity, track.entity.artist)
  if (repetido >= 2) {
    const pen = Math.min(MAX_PENALIDAD_ARTISTA, PENALIDAD_ARTISTA_REPETIDO * repetido)
    factor *= 1 - pen
    reasons.push(
      `${pen > 0 ? NEGATIVA : ''}ya guardaste ${repetido} de ${track.entity.artist}: mismo artista, no un hallazgo`,
    )
  }

  return { total: Math.round((total / wsum) * factor * 100), components, reasons }
}

/** Etiqueta para la UI según el score. */
export function scoreLabel(total: number): string {
  if (total >= 85) return '🔥 Hidden Gem'
  if (total >= 70) return '✦ Strong dig'
  if (total >= 55) return 'Worth a listen'
  return 'Deep cut'
}
