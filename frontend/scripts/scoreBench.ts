/**
 * scoreBench — mide el CRATE Score contra el oído real de Thomas.
 *
 * Lee el benchmark congelado de `docs/benchmarks/2026-09-19-digging-a-mano/`
 * (1.958 items de 10 playlists ajenas, 206 sugerencias, 109 guardadas), arma
 * fichas mínimas como las armaría el pipeline SIN catálogo (título, uploader,
 * views aproximadas, año verificado, BPM crudo del DSP), siembra la affinity con
 * lo que Thomas tenía en sus 5 playlists ANTES de ese día, y mide cuánto separa
 * `computeCrateScore` lo que guardó de lo que no.
 *
 * Dos conjuntos, dos preguntas:
 *   - `sugeridos` (199 ids únicos, 106 guardados): Thomas escuchó TODO esto. Es
 *     la etiqueta fuerte: ¿el score ordena arriba lo que le sirvió?
 *   - `pool` (1.958 items, 109 guardados): el resto no lo vio. Etiqueta débil:
 *     ¿el score sube lo guardado por encima de lo que ni se sugirió?
 *
 * Métricas: AUC (Mann-Whitney: probabilidad de que un guardado puntúe arriba de
 * un no guardado; 0.5 = azar) del total y de cada componente, y precisión@30
 * (de los 30 mejores, cuántos guardó). Se compara contra la tasa base.
 *
 * Lo que este benchmark NO tiene: want/have ni créditos de Discogs (rarity y
 * richness quedan planos), y las views vienen redondeadas de `--flat-playlist`.
 * Mide los componentes metadata-free: obscurity, historical, source quality,
 * affinity y tempo.
 *
 * Correr desde `frontend/`:
 *   npx tsx scripts/scoreBench.ts [--top 30] [--pool-top] [--json] [--weights obscurity=0.1,sourceQuality=0.2]
 *
 * Reporta siempre dos variantes de `core/canales.ts`: con la lista entera y
 * sin las entradas sembradas desde este mismo benchmark (circulares). El
 * número que vale es el segundo.
 */
import { readFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { EnrichedTrack, SourceItem } from '../src/core/entities'
import { computeCrateScore, DEFAULT_WEIGHTS, type ScoreComponents } from '../src/core/score'
import { emptyAffinity, learn, type Affinity } from '../src/core/affinity'
import { analyzed } from '../src/core/provenance'
import { splitArtistTitle, extractYear } from '../src/core/fuzzy'
import type { SceneId } from '../src/core/scenes'
import { foldBpm } from '../src/core/tempo'
import { tasteTempoRange } from '../src/core/affinity'
import { CANALES, indexarCanales } from '../src/core/canales'

// ---------- datos del benchmark ----------

interface PoolItem {
  video_id: string
  title: string
  uploader: string | null
  channel_id: string | null
  duration_sec: number | null
  views_approx: number | null
  playlist_vol: number
  playlist_index: number
  unavailable: boolean
}

interface LabelRow {
  entrega: 'soul' | 'rnb' | 'citypop' | 'fusion' | '80s'
  id: string
  tier: 'fuego' | 'bien' | 'quizas' | 'no_rankeado'
  saved: boolean
  dest: string[]
}

interface VerificacionRow {
  playlist: string
  id: string
  fits: 'si' | 'quizas' | 'no'
  bpm: number | null
  bpm_raw: number | null
  key: string | null
  year: string | number | null
  instruments: string | null
  why: string
}

interface PlaylistItem {
  video_id: string
  title: string
  uploader: string
}

type PlaylistsThomas = Record<
  string,
  { playlist_id: string; before_2026_09_19: PlaylistItem[]; after_2026_09_20: PlaylistItem[] }
>

interface Descripcion {
  year: string | null
  phonogram: boolean
  uploader: string
  title: string
  desc: string
}

interface OctavaRow {
  id: string
  raw: number
  final: number
  conf: number
}

const HERE = dirname(fileURLToPath(import.meta.url))
const BENCH = resolve(HERE, '../../docs/benchmarks/2026-09-19-digging-a-mano')

function leer<T>(nombre: string): T {
  return JSON.parse(readFileSync(resolve(BENCH, nombre), 'utf8')) as T
}

const pool = leer<PoolItem[]>('pool.json')
const labels = leer<LabelRow[]>('labels.json')
const verificacion = leer<VerificacionRow[]>('verificacion.json')
const playlists = leer<PlaylistsThomas>('playlists_thomas.json')
const descripciones = leer<Record<string, Partial<Descripcion>>>('descripciones.json')
const octavas = leer<OctavaRow[]>('bpm_octave_dataset.json')

const poolPorId = new Map(pool.map((p) => [p.video_id, p]))
const verPorId = new Map<string, VerificacionRow>()
for (const v of verificacion) if (!verPorId.has(v.id)) verPorId.set(v.id, v)
const confPorId = new Map(octavas.map((o) => [o.id, o.conf]))

/** el uploader de las playlists de Thomas no trae channel_id: se resuelve por el pool */
const channelDeUploader = new Map<string, string>()
for (const p of pool) if (p.uploader && p.channel_id) channelDeUploader.set(p.uploader, p.channel_id)

// ---------- escenas por entrega (lo que el plan de digging sabría) ----------

const ESCENAS_POR_ENTREGA: Record<LabelRow['entrega'], SceneId[]> = {
  '80s': ['quiet-storm', 'modern-soul'],
  soul: ['deep-soul-70s', 'soul-jazz'],
  rnb: ['quiet-storm', 'modern-soul'],
  citypop: ['city-pop'],
  fusion: ['jazz-fusion'],
}

// ---------- fichas mínimas ----------

function anioDe(v: string | number | null | undefined): number | undefined {
  if (v == null) return undefined
  const m = String(v).match(/(19[2-9]\d|20[0-2]\d)/)
  return m ? Number(m[1]) : undefined
}

/**
 * "Artista - Topic" identifica al artista, salvo los Topic genéricos de YouTube
 * ("Release - Topic", "Various Artists - Topic"), que no dicen quién es.
 */
function artistaDeTopic(uploader: string | null | undefined): string | undefined {
  const m = (uploader ?? '').match(/^(.*) - Topic$/)
  if (!m) return undefined
  const a = m[1].trim()
  return /^(release|various artists?)$/i.test(a) ? undefined : a
}

function fuente(p: PoolItem): SourceItem {
  return {
    id: `youtube:${p.video_id}`,
    kind: 'youtube',
    nativeId: p.video_id,
    url: `https://www.youtube.com/watch?v=${p.video_id}`,
    title: p.title,
    uploader: p.uploader ?? undefined,
    channelId: p.channel_id ?? undefined,
    durationSec: p.duration_sec ?? undefined,
    views: p.views_approx ?? undefined,
    viewsApprox: true,
  }
}

/**
 * La ficha como la armaría `enrichOne` sin cruce contra catálogo: artista del
 * canal Topic o del split del título; año del ℗ (hint duro) o del verificado;
 * BPM crudo del DSP con su confianza (lo que llega hoy del backend).
 */
function ficha(p: PoolItem, soloFuente = false): EnrichedTrack {
  const now = '2026-09-19T00:00:00.000Z'
  // en el pool, verificación y descripciones existen SOLO para los candidatos
  // que pasaron la primera lente: usarlas ahí sería una fuga de la etiqueta
  const v = soloFuente ? undefined : verPorId.get(p.video_id)
  const d = soloFuente ? undefined : descripciones[p.video_id]
  const topic = artistaDeTopic(p.uploader)
  const split = splitArtistTitle(p.title)
  const artist = topic ?? split.artist ?? 'Unknown'
  const title = topic ? p.title : (split.title ?? p.title)
  const phonogram = d?.phonogram === true
  const year = (phonogram ? anioDe(d?.year) : undefined) ?? anioDe(v?.year) ?? extractYear(p.title)
  const bpmRaw = v?.bpm_raw ?? undefined
  return {
    crateId: `bench:${p.video_id}`,
    entity: {
      crateId: `bench:${p.video_id}`,
      artist,
      title,
      year,
      genres: [],
      styles: [],
      credits: [],
      confirmed: phonogram,
      identifiedBy: phonogram ? 'topic_channel' : undefined,
    },
    sources: [fuente(p)],
    bpm: bpmRaw != null ? analyzed(bpmRaw, confPorId.get(p.video_id) ?? 0.5) : undefined,
    key: v?.key ? analyzed(v.key, 0.5) : undefined,
    rarity: { youtubeViews: p.views_approx ?? undefined },
    status: 'seen',
    firstSeenAt: now,
    updatedAt: now,
  }
}

/** Una ficha de sus playlists de antes: solo título + uploader, como las importa la app. */
function fichaPropia(it: PlaylistItem, tag: string): EnrichedTrack {
  const now = '2026-09-18T00:00:00.000Z'
  const topic = artistaDeTopic(it.uploader)
  const split = splitArtistTitle(it.title)
  const enPool = poolPorId.get(it.video_id)
  return {
    crateId: `own:${it.video_id}`,
    entity: {
      crateId: `own:${it.video_id}`,
      artist: topic ?? split.artist ?? 'Unknown',
      title: topic ? it.title : (split.title ?? it.title),
      genres: [],
      styles: [],
      credits: [],
      // un canal Topic ES la metadata del distribuidor: identifica al artista
      confirmed: Boolean(topic),
      identifiedBy: topic ? 'topic_channel' : undefined,
    },
    sources: [
      {
        id: `youtube:${it.video_id}`,
        kind: 'youtube',
        nativeId: it.video_id,
        url: `https://www.youtube.com/watch?v=${it.video_id}`,
        title: it.title,
        uploader: it.uploader,
        channelId: enPool?.channel_id ?? channelDeUploader.get(it.uploader),
      },
    ],
    rarity: {},
    tags: [tag],
    status: 'saved',
    firstSeenAt: now,
    updatedAt: now,
  }
}

// ---------- métricas ----------

/** Mann-Whitney: P(score(guardado) > score(no guardado)), empates a 0.5. */
function auc(pos: number[], neg: number[]): number {
  if (!pos.length || !neg.length) return NaN
  let s = 0
  for (const p of pos) for (const n of neg) s += p > n ? 1 : p === n ? 0.5 : 0
  return s / (pos.length * neg.length)
}

interface Puntuado {
  id: string
  entregas: string[]
  saved: boolean
  total: number
  components: ScoreComponents
  reasons: string[]
  views: number
}

function precisionAt(items: Puntuado[], k: number): number {
  const top = [...items].sort((a, b) => b.total - a.total).slice(0, k)
  return top.filter((t) => t.saved).length / top.length
}

function mediana(xs: number[]): number {
  const s = [...xs].sort((a, b) => a - b)
  return s.length ? s[Math.floor(s.length / 2)] : NaN
}

function reporte(nombre: string, items: Puntuado[], top: number): Record<string, number> {
  const pos = items.filter((i) => i.saved)
  const neg = items.filter((i) => !i.saved)
  const out: Record<string, number> = {}
  out.n = items.length
  out.guardados = pos.length
  out.tasaBase = pos.length / items.length
  out.auc = auc(
    pos.map((i) => i.total),
    neg.map((i) => i.total),
  )
  out[`p@${top}`] = precisionAt(items, top)
  out.medianaGuardados = mediana(pos.map((i) => i.total))
  out.medianaNoGuardados = mediana(neg.map((i) => i.total))
  for (const k of Object.keys(DEFAULT_WEIGHTS) as (keyof ScoreComponents)[]) {
    out[`auc.${k}`] = auc(
      pos.map((i) => i.components[k]),
      neg.map((i) => i.components[k]),
    )
  }
  console.log(`\n== ${nombre} ==`)
  console.log(
    `n=${out.n}  guardados=${out.guardados}  tasa base=${out.tasaBase.toFixed(3)}  ` +
      `AUC=${out.auc.toFixed(3)}  p@${top}=${out[`p@${top}`].toFixed(3)}  ` +
      `mediana score guardados=${out.medianaGuardados} / no=${out.medianaNoGuardados}`,
  )
  console.log('  AUC por componente:')
  for (const k of Object.keys(DEFAULT_WEIGHTS) as (keyof ScoreComponents)[]) {
    const v = out[`auc.${k}`]
    console.log(`    ${k.padEnd(20)} ${Number.isNaN(v) ? '  -  ' : v.toFixed(3)}`)
  }
  return out
}

// ---------- correr ----------

const args = process.argv.slice(2)
const top = Number(args[args.indexOf('--top') + 1]) || 30
const json = args.includes('--json')

/** `--weights obscurity=0.1,sourceQuality=0.2` para probar pesos sin tocar score.ts */
const pesos: ScoreComponents = { ...DEFAULT_WEIGHTS }
const wArg = args.indexOf('--weights')
if (wArg >= 0) {
  for (const par of (args[wArg + 1] ?? '').split(',')) {
    const [k, v] = par.split('=')
    if (k in pesos && Number.isFinite(Number(v))) pesos[k as keyof ScoreComponents] = Number(v)
  }
  console.log('pesos:', JSON.stringify(pesos))
}

// 1) affinity sembrada con lo que tenía ANTES
let affinity: Affinity = emptyAffinity()
let sembrados = 0
for (const [nombre, pl] of Object.entries(playlists)) {
  for (const it of pl.before_2026_09_19) {
    affinity = learn(affinity, fichaPropia(it, nombre), 1)
    sembrados++
  }
}
const cuenta = (c: Record<string, number>): number => Object.keys(c).length
console.log(
  `affinity sembrada con ${sembrados} temas de sus playlists (total=${affinity.total}): ` +
    `${cuenta(affinity.channels)} canales, ${cuenta(affinity.artists)} artistas, ` +
    `${cuenta(affinity.eras)} épocas, ${cuenta(affinity.bpmBuckets)} buckets de BPM`,
)

// 2) sugeridos: ids únicos, positivo si lo guardó en cualquier entrega
const sugeridos = new Map<string, { saved: boolean; escenas: Set<SceneId>; entregas: string[] }>()
for (const l of labels) {
  if (l.tier === 'no_rankeado') continue
  const s = sugeridos.get(l.id) ?? { saved: false, escenas: new Set<SceneId>(), entregas: [] }
  s.saved = s.saved || l.saved
  s.entregas.push(l.entrega)
  for (const e of ESCENAS_POR_ENTREGA[l.entrega]) s.escenas.add(e)
  sugeridos.set(l.id, s)
}
const guardadosEnPool = new Set(labels.filter((l) => l.saved).map((l) => l.id))

const query = { text: '' }

function puntuarTodo(): { sugeridos: Puntuado[]; pool: Puntuado[] } {
  const sug: Puntuado[] = []
  for (const [id, s] of sugeridos) {
    const p = poolPorId.get(id)
    if (!p) continue
    const t = ficha(p)
    const score = computeCrateScore(t, query, affinity, pesos, {
      escenas: [...s.escenas],
      origen: 'veta',
    })
    sug.push({
      id,
      entregas: s.entregas,
      saved: s.saved,
      total: score.total,
      components: score.components,
      reasons: score.reasons,
      views: p.views_approx ?? 0,
    })
  }

  const vistos = new Set<string>()
  const todo: Puntuado[] = pool
    .filter((p) => !p.unavailable && !vistos.has(p.video_id) && vistos.add(p.video_id))
    .map((p) => {
      const t = ficha(p, true)
      const score = computeCrateScore(t, query, affinity, pesos, { origen: 'veta' })
      return {
        id: p.video_id,
        entregas: [],
        saved: guardadosEnPool.has(p.video_id),
        total: score.total,
        components: score.components,
        reasons: score.reasons,
        views: p.views_approx ?? 0,
      }
    })
  return { sugeridos: sug, pool: todo }
}

/**
 * Dos variantes de `CANALES`, porque la lista se sembró desde ESTE benchmark
 * (`guardados: N` y los canales de ruido salieron del pool): con la lista
 * entera, sourceQuality y affinity puntúan con la etiqueta que se está
 * midiendo. La variante "sin sembrados" deja solo los curadores del brief
 * que no vienen de acá: es el número honesto (vetaBench hace lo mismo).
 */
const { sugeridos: puntuarSugeridos, pool: puntuarPool } = puntuarTodo()
const canalesSembrados = CANALES.filter((c) => c.guardados != null || c.rol === 'ruido')
indexarCanales(CANALES.filter((c) => !canalesSembrados.includes(c)))
const sinSembrados = puntuarTodo()
indexarCanales()

const rSug = reporte('sugeridos (etiqueta fuerte: escuchó todo)', puntuarSugeridos, top)
console.log('  por entrega (AUC / p@10 / n / guardados) — 80s no tiene verificación ni ℗:')
for (const e of Object.keys(ESCENAS_POR_ENTREGA)) {
  const items = puntuarSugeridos.filter((i) => i.entregas.includes(e))
  const pos = items.filter((i) => i.saved)
  const neg = items.filter((i) => !i.saved)
  console.log(
    `    ${e.padEnd(8)} AUC=${auc(pos.map((i) => i.total), neg.map((i) => i.total)).toFixed(3)}  ` +
      `p@10=${precisionAt(items, 10).toFixed(2)}  n=${items.length}  guardados=${pos.length}`,
  )
}
const rPool = reporte(
  'pool entero, solo metadata del flat (etiqueta débil: lo no sugerido no lo vio)',
  puntuarPool,
  top,
)

// la misma medición sin las entradas de CANALES que salieron de este benchmark
const aucDe = (items: Puntuado[], k?: keyof ScoreComponents): number =>
  auc(
    items.filter((i) => i.saved).map((i) => (k ? i.components[k] : i.total)),
    items.filter((i) => !i.saved).map((i) => (k ? i.components[k] : i.total)),
  )
console.log(
  `\n== CANALES: con la lista entera vs sin las ${canalesSembrados.length} entradas sembradas desde este benchmark (número honesto) ==`,
)
console.log(`  ${''.padEnd(20)} ${'sugeridos'.padStart(15)}   ${'pool'.padStart(15)}`)
console.log(`  ${''.padEnd(20)} ${'con'.padStart(7)} ${'sin'.padStart(7)}   ${'con'.padStart(7)} ${'sin'.padStart(7)}`)
const filaAuc = (nombre: string, k?: keyof ScoreComponents): void =>
  console.log(
    `  ${nombre.padEnd(20)} ${aucDe(puntuarSugeridos, k).toFixed(3).padStart(7)} ${aucDe(sinSembrados.sugeridos, k).toFixed(3).padStart(7)}   ` +
      `${aucDe(puntuarPool, k).toFixed(3).padStart(7)} ${aucDe(sinSembrados.pool, k).toFixed(3).padStart(7)}`,
  )
filaAuc('AUC total')
filaAuc('  sourceQuality', 'sourceQuality')
filaAuc('  personalAffinity', 'personalAffinity')
console.log(
  `  p@${top} pool: con ${precisionAt(puntuarPool, top).toFixed(3)} · sin ${precisionAt(sinSembrados.pool, top).toFixed(3)}`,
)
const rSinCanales = {
  sugeridos: { auc: aucDe(sinSembrados.sugeridos), 'auc.sourceQuality': aucDe(sinSembrados.sugeridos, 'sourceQuality') },
  pool: { auc: aucDe(sinSembrados.pool), 'auc.sourceQuality': aucDe(sinSembrados.pool, 'sourceQuality'), [`p@${top}`]: precisionAt(sinSembrados.pool, top) },
}

// 3) muestra del top: qué dice el Why this
console.log(`\n== top 12 de sugeridos ==`)
for (const it of [...puntuarSugeridos].sort((a, b) => b.total - a.total).slice(0, 12)) {
  const p = poolPorId.get(it.id)
  console.log(
    `  ${it.saved ? 'SI ' : 'no '} ${String(it.total).padStart(3)}  ${(p?.title ?? '').slice(0, 60).padEnd(60)}  ~${it.views.toLocaleString()} views`,
  )
  for (const r of it.reasons) console.log(`        · ${r}`)
}

// 4) octava: ¿cuánto acierta el BPM plegado contra el juicio musical?
{
  const prior = tasteTempoRange(affinity)
  const ok = (a: number, b: number): boolean => Math.abs(a - b) <= 2
  const crudo = octavas.filter((o) => ok(o.raw, o.final)).length
  const plegado = octavas.filter((o) =>
    ok(foldBpm(o.raw, undefined, prior, { confidence: o.conf }).value, o.final),
  ).length
  console.log(
    `
== octava del BPM (${octavas.length} pares crudo/juicio) ==
` +
      `  prior ${prior.min}–${prior.max} (${affinity.total >= 30 && Object.keys(affinity.bpmBuckets).length ? 'aprendido' : 'default'})  ` +
      `crudo acierta ${crudo} (${((100 * crudo) / octavas.length).toFixed(1)}%)  ` +
      `plegado acierta ${plegado} (${((100 * plegado) / octavas.length).toFixed(1)}%)`,
  )
}

if (args.includes('--pool-top')) {
  console.log(`
== top ${top} del pool ==`)
  for (const it of [...puntuarPool].sort((a, b) => b.total - a.total).slice(0, top)) {
    const p = poolPorId.get(it.id)
    const c = it.components
    console.log(
      `  ${it.saved ? 'SI ' : 'no '} ${String(it.total).padStart(3)}  ${(p?.title ?? '').slice(0, 48).padEnd(48)} ` +
        `${(p?.uploader ?? '').slice(0, 22).padEnd(22)} ~${it.views.toLocaleString().padStart(9)}  ` +
        `obs=${c.obscurity.toFixed(2)} src=${c.sourceQuality.toFixed(2)} hist=${c.historicalRelevance.toFixed(2)} aff=${c.personalAffinity.toFixed(2)}`,
    )
  }
}

if (json) {
  console.log(JSON.stringify({ sugeridos: rSug, pool: rPool, sinCanalesSembrados: rSinCanales }, null, 2))
}
