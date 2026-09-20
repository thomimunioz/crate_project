/**
 * vetaBench — mide el flujo de "cavar una veta por tandas" contra el benchmark
 * del 19-sep (docs/benchmarks/2026-09-19-digging-a-mano), sin red.
 *
 *   npx tsx scripts/vetaBench.ts [--tanda 24] [--dump]
 *
 * Simula las 10 playlists "Samples Vol." como 10 vetas: cada una se lista en
 * tandas de 200 (como el backend), pasa por `sumarAlPool` (borrados, basura
 * dura, misma obra repetida) y se cava con `proximaTanda` de a 24, marcando
 * seen entre tandas (el cursor real). Reporta:
 *
 *   - cobertura: cuántos se cavan, cuántos se descartan y por qué, y —lo que
 *     importa— cuántos de los 106 guardados por Thomas caen descartados (tiene
 *     que ser 0: la joya no se anuncia en el título).
 *   - cursor: ningún id se cava dos veces; con seen previo, se salta.
 *   - orden barato: en qué tanda cae cada guardado con `proximaTanda` contra
 *     el orden de la playlist (baseline). Sin catálogo ni affinity rica, el
 *     orden solo decide por dónde empezar; acá se mide si empieza mejor.
 *
 * La affinity se siembra con las 5 playlists de Thomas de ANTES (como en
 * scoreBench): es lo que la app tendría al importarlas.
 */
import { readFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

import type { EnrichedTrack, SourceItem } from '../src/core/entities'
import { emptyAffinity, learn, type Affinity } from '../src/core/affinity'
import { splitArtistTitle } from '../src/core/fuzzy'
import { sumarAlPool, proximaTanda, type EstadoDeVeta, type OpcionesDeTanda } from '../src/pipeline'
import { timesFromChannel } from '../src/core/affinity'
import { esCurador } from '../src/core/canales'
import type { TandaDeVeta } from '../src/sources/youtube'

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
  entrega: string
  id: string
  tier: string
  saved: boolean
  dest: string[]
}

interface PlaylistItem {
  video_id: string
  title: string
  uploader: string
}

type PlaylistsThomas = Record<string, { playlist_id: string; before_2026_09_19: PlaylistItem[] }>

const HERE = dirname(fileURLToPath(import.meta.url))
const BENCH = resolve(HERE, '../../docs/benchmarks/2026-09-19-digging-a-mano')
const leer = <T>(nombre: string): T => JSON.parse(readFileSync(resolve(BENCH, nombre), 'utf8')) as T

const args = process.argv.slice(2)
const flag = (k: string, def: number): number => {
  const i = args.indexOf(k)
  return i >= 0 ? Number(args[i + 1]) : def
}
const TANDA = flag('--tanda', 24)
const DUMP = args.includes('--dump')
const PAGINA = 200

const pool = leer<PoolItem[]>('pool.json')
const labels = leer<LabelRow[]>('labels.json')
const playlists = leer<PlaylistsThomas>('playlists_thomas.json')

const guardados = new Set(labels.filter((l) => l.saved).map((l) => l.id))
const sugeridos = new Set(labels.filter((l) => l.tier !== 'no_rankeado').map((l) => l.id))

// ---------- affinity sembrada con sus playlists de antes ----------

const channelDeUploader = new Map<string, string>()
for (const p of pool) if (p.uploader && p.channel_id) channelDeUploader.set(p.uploader, p.channel_id)

function fichaPropia(it: PlaylistItem, tag: string): EnrichedTrack {
  const now = '2026-09-18T00:00:00.000Z'
  const topic = / - Topic$/.test(it.uploader) ? it.uploader.replace(/ - Topic$/, '') : undefined
  const split = splitArtistTitle(it.title)
  return {
    crateId: `own:${it.video_id}`,
    entity: {
      crateId: `own:${it.video_id}`,
      artist: topic ?? split.artist ?? 'Unknown',
      title: topic ? it.title : (split.title ?? it.title),
      genres: [],
      styles: [],
      credits: [],
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
        channelId: channelDeUploader.get(it.uploader),
      },
    ],
    rarity: {},
    tags: [tag],
    status: 'saved',
    firstSeenAt: now,
    updatedAt: now,
  }
}

let affinity: Affinity = emptyAffinity()
const yaTenia = new Set<string>()
for (const [nombre, pl] of Object.entries(playlists)) {
  for (const it of pl.before_2026_09_19) {
    affinity = learn(affinity, fichaPropia(it, nombre.toLowerCase()))
    yaTenia.add(it.video_id)
  }
}

// ---------- el pool como lo devolvería el backend ----------

function tandaDe(vol: number, items: PoolItem[], offset: number): TandaDeVeta {
  const pagina = items.slice(offset, offset + PAGINA)
  const disponibles = pagina.filter((p) => !p.unavailable)
  return {
    kind: 'playlist',
    id: `PL-vol-${vol}`,
    nombre: `Samples Vol. ${String(vol).padStart(2, '0')}`,
    total: items.length,
    offset,
    nextOffset: offset + PAGINA < items.length ? offset + PAGINA : undefined,
    noDisponibles: pagina.length - disponibles.length,
    items: disponibles.map(
      (p): SourceItem => ({
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
        playlistIndex: p.playlist_index,
      }),
    ),
  }
}

const porVol = new Map<number, PoolItem[]>()
for (const p of pool) porVol.set(p.playlist_vol, [...(porVol.get(p.playlist_vol) ?? []), p])
for (const items of porVol.values()) items.sort((a, b) => a.playlist_index - b.playlist_index)

// ---------- simulación ----------

interface Resultado {
  vol: number
  total: number
  cavados: number
  descartados: number
  saltados: number
  tandas: number
  /** tanda (1-based) en que cayó cada guardado, con proximaTanda */
  tandaDeGuardado: number[]
  /** idem con el orden de la playlist */
  tandaBaseline: number[]
  guardadosDescartados: string[]
  cavadosDosVeces: number
}

const query = { text: '' }

/**
 * Variantes del orden barato, para saber qué señal aporta cuánto. OJO:
 * `CANALES` (core/canales.ts) se sembró con ESTE benchmark, así que la variante
 * "curador" es circular acá; la honesta es "solo affinity" (sus playlists de
 * antes, que la app tendría al importarlas).
 */
const VARIANTES: Record<string, OpcionesDeTanda['prioridad']> = {
  'affinity+curador (default)': undefined,
  'solo affinity': (i) => timesFromChannel(affinity, i) > 0,
  'solo curador': (i) => esCurador(i.channelId, i.uploader),
  'sin prioridad': () => false,
}

function simular(vol: number, items: PoolItem[], seenPrevio: Set<string>, prioridad?: OpcionesDeTanda['prioridad']): Resultado {
  const veta = { kind: 'playlist' as const, ref: `PL-vol-${vol}` }
  let estado: EstadoDeVeta = { veta, nombre: veta.ref, listados: 0, descartados: 0, nextOffset: 0, pool: [] }
  const seen = new Set(seenPrevio)
  const cavados = new Map<string, number>() // id → tanda
  let tandas = 0
  let saltados = 0
  let dosVeces = 0

  for (;;) {
    while (estado.pool.filter((i) => !seen.has(i.id)).length < TANDA && estado.nextOffset != null) {
      estado = sumarAlPool(estado, tandaDe(vol, items, estado.nextOffset))
    }
    const paso = proximaTanda(estado, query, affinity, seen, { n: TANDA, prioridad })
    estado = paso.estado
    saltados += paso.saltados
    if (paso.tanda.length === 0) break
    tandas++
    for (const it of paso.tanda) {
      if (cavados.has(it.id)) dosVeces++
      cavados.set(it.id, tandas)
      seen.add(it.id)
    }
  }

  // baseline: orden de la playlist, mismos descartes
  const idsCavados = [...cavados.keys()]
  const enOrden = items.filter((p) => idsCavados.includes(`youtube:${p.video_id}`)).map((p) => `youtube:${p.video_id}`)
  const tandaBase = new Map(enOrden.map((id, i) => [id, Math.floor(i / TANDA) + 1]))

  const tandaDeGuardado: number[] = []
  const tandaBaseline: number[] = []
  const guardadosDescartados: string[] = []
  for (const p of items) {
    if (!guardados.has(p.video_id)) continue
    const id = `youtube:${p.video_id}`
    if (seenPrevio.has(id)) continue
    const t = cavados.get(id)
    if (t == null) {
      guardadosDescartados.push(`${p.video_id} · ${p.title} · ${p.duration_sec ?? '?'}s`)
      continue
    }
    tandaDeGuardado.push(t)
    tandaBaseline.push(tandaBase.get(id) ?? 0)
  }

  return {
    vol,
    total: items.length,
    cavados: cavados.size,
    descartados: estado.descartados,
    saltados,
    tandas,
    tandaDeGuardado,
    tandaBaseline,
    guardadosDescartados,
    cavadosDosVeces: dosVeces,
  }
}

const media = (xs: number[]): number => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : NaN)
const f1 = (x: number): string => (Number.isNaN(x) ? '—' : x.toFixed(1))
const f2 = (x: number): string => (Number.isNaN(x) ? '—' : x.toFixed(2))

// 1) sin seen previo
const seenVacio = new Set<string>()
const res = [...porVol.entries()].map(([vol, items]) => simular(vol, items, seenVacio))

console.log(`\nvetaBench · ${pool.length} items en ${porVol.size} vetas · tanda=${TANDA} · guardados=${guardados.size} · sugeridos=${sugeridos.size}\n`)
console.log('vol  total  cavados  descart  tandas  guardados  tanda media (proxima / playlist)  1ª tanda (prox / base / azar)')
let totCav = 0
let totDesc = 0
let totTandas = 0
const todasProx: number[] = []
const todasBase: number[] = []
let primeraProx = 0
let primeraBase = 0
let primeraAzar = 0
let guardadosDesc: string[] = []
let dosVeces = 0
for (const r of res) {
  totCav += r.cavados
  totDesc += r.descartados
  totTandas += r.tandas
  todasProx.push(...r.tandaDeGuardado)
  todasBase.push(...r.tandaBaseline)
  const g = r.tandaDeGuardado.length
  const p1 = r.tandaDeGuardado.filter((t) => t === 1).length
  const b1 = r.tandaBaseline.filter((t) => t === 1).length
  const azar = r.cavados ? (g * TANDA) / r.cavados : 0
  primeraProx += p1
  primeraBase += b1
  primeraAzar += azar
  guardadosDesc = guardadosDesc.concat(r.guardadosDescartados)
  dosVeces += r.cavadosDosVeces
  console.log(
    `${String(r.vol).padStart(3)}  ${String(r.total).padStart(5)}  ${String(r.cavados).padStart(7)}  ${String(r.descartados).padStart(7)}  ${String(r.tandas).padStart(6)}  ${String(g).padStart(9)}  ${f1(media(r.tandaDeGuardado)).padStart(8)} / ${f1(media(r.tandaBaseline)).padEnd(8)}          ${String(p1).padStart(2)} / ${String(b1).padStart(2)} / ${f1(azar)}`,
  )
}
console.log(
  `tot  ${String(pool.length).padStart(5)}  ${String(totCav).padStart(7)}  ${String(totDesc).padStart(7)}  ${String(totTandas).padStart(6)}  ${String(todasProx.length).padStart(9)}  ${f1(media(todasProx)).padStart(8)} / ${f1(media(todasBase)).padEnd(8)}          ${String(primeraProx).padStart(2)} / ${String(primeraBase).padStart(2)} / ${f1(primeraAzar)}`,
)

// tasa de guardado en la primera tanda vs base
const tasaBase = todasProx.length / totCav
const tasa1 = primeraProx / (res.length * TANDA)
console.log(
  `\nprimera tanda: ${primeraProx} guardados en ${res.length * TANDA} fichas = ${(tasa1 * 100).toFixed(1)}% (tasa base del pool cavado ${(tasaBase * 100).toFixed(1)}%, ×${f2(tasa1 / tasaBase)})`,
)
console.log(`cobertura: ${totCav} cavados + ${totDesc} descartados = ${totCav + totDesc} de ${pool.length}`)
console.log(`guardados descartados sin cavar: ${guardadosDesc.length} (tiene que ser 0)`)
for (const g of guardadosDesc) console.log(`   ✗ ${g}`)
console.log(`ids cavados dos veces: ${dosVeces} (tiene que ser 0)`)

// 1b) qué aporta cada señal del orden barato
console.log('\norden barato por variante (guardados en la 1ª tanda de las 10 vetas / tanda media del guardado):')
for (const [nombre, prioridad] of Object.entries(VARIANTES)) {
  const rs = [...porVol.entries()].map(([vol, items]) => simular(vol, items, seenVacio, prioridad))
  const p1 = rs.reduce((s, r) => s + r.tandaDeGuardado.filter((t) => t === 1).length, 0)
  const tm = media(rs.flatMap((r) => r.tandaDeGuardado))
  console.log(`   ${nombre.padEnd(28)} ${String(p1).padStart(3)} / 240 = ${((p1 / 240) * 100).toFixed(1).padStart(5)}% · tanda media ${f1(tm)}`)
}
console.log(`   ${'orden de la playlist'.padEnd(28)} ${String(primeraBase).padStart(3)} / 240 = ${((primeraBase / 240) * 100).toFixed(1).padStart(5)}% · tanda media ${f1(media(todasBase))}`)

// 2) con seen previo: lo que Thomas ya tenía en sus playlists + la primera tanda de cada veta
const seenPrevio = new Set<string>()
for (const id of yaTenia) seenPrevio.add(`youtube:${id}`)
const enPoolYaVisto = pool.filter((p) => yaTenia.has(p.video_id)).length
const res2 = [...porVol.entries()].map(([vol, items]) => simular(vol, items, seenPrevio))
const cav2 = res2.reduce((s, r) => s + r.cavados, 0)
const salt2 = res2.reduce((s, r) => s + r.saltados, 0)
const dos2 = res2.reduce((s, r) => s + r.cavadosDosVeces, 0)
console.log(
  `\ncursor = seen: con sus 5 playlists importadas (${yaTenia.size} ids, ${enPoolYaVisto} en el pool) se saltan ${salt2} y se cavan ${cav2} (${totCav - cav2} menos); cavados dos veces: ${dos2}`,
)

// 3) chequeos
const fallos: string[] = []
if (guardadosDesc.length) fallos.push(`${guardadosDesc.length} guardados descartados por el portero`)
if (dosVeces || dos2) fallos.push('hay ids cavados dos veces')
if (totCav + totDesc !== pool.length) fallos.push('la cobertura no cierra')
if (salt2 !== enPoolYaVisto) fallos.push(`saltados ${salt2} ≠ ya vistos en el pool ${enPoolYaVisto}`)

if (DUMP) {
  console.log('\n— descartados por vol (basura dura / borrados / repetidos) —')
  for (const [vol, items] of porVol) {
    let estado: EstadoDeVeta = {
      veta: { kind: 'playlist', ref: `v${vol}` },
      nombre: `v${vol}`,
      listados: 0,
      descartados: 0,
      nextOffset: 0,
      pool: [],
    }
    while (estado.nextOffset != null) estado = sumarAlPool(estado, tandaDe(vol, items, estado.nextOffset))
    const enPool = new Set(estado.pool.map((i) => i.nativeId))
    for (const p of items) {
      if (!enPool.has(p.video_id)) console.log(`  v${vol} ${p.unavailable ? '[borrado]' : ''} ${p.duration_sec ?? '?'}s · ${p.title} · ${p.uploader ?? ''}`)
    }
  }
}

console.log(`\n${fallos.length ? `FALLOS: ${fallos.join(' · ')}` : 'chequeos: ok'}`)
process.exit(fallos.length ? 1 : 0)
