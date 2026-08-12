/**
 * YouTube Data API v3 — la fuente de descubrimiento principal.
 * CORS OK desde el browser con API key. Cuidar la quota: search.list = 100 unidades.
 * Ver docs/SOURCES.md
 */
import type { SourceItem, SearchQuery } from '@/core/entities'
import type { DiscoverySource } from './types'
import { discoverIds } from '@/api/backend'
import {
  planificarQueries,
  esBasura,
  ordenarParaDigging,
  MAX_RESULTS_POR_BUSQUEDA,
  PRESUPUESTO_POR_DEFECTO,
  type CandidatoDeDigging,
  type DiggerQuery,
  type PlanDeDigging,
} from '@/core/queries'
import { ESCENAS, obviosDe } from '@/core/scenes'

const KEY = import.meta.env.VITE_YOUTUBE_API_KEY
const BASE = 'https://www.googleapis.com/youtube/v3'

/** Cuántos candidatos devolver al pipeline. Enriquece 24; el resto es colchón
 *  para cuando "no me muestres lo que ya vi" descarta la mitad. */
const CANDIDATOS_POR_BUSQUEDA = 48

/** Convierte 'PT3M25S' a segundos. */
function parseISODuration(iso: string): number | undefined {
  const m = iso.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/)
  if (!m) return undefined
  const [, h, mm, s] = m
  return (Number(h ?? 0) * 3600) + (Number(mm ?? 0) * 60) + Number(s ?? 0)
}

/** videos.list = 1 unidad y acepta hasta 50 ids por request. Barato: trae stats + duración. */
async function fetchStats(ids: string[]): Promise<Map<string, any>> {
  const out = new Map<string, any>()
  for (let i = 0; i < ids.length; i += 50) {
    const params = new URLSearchParams({
      part: 'statistics,contentDetails,snippet',
      id: ids.slice(i, i + 50).join(','),
      key: KEY,
    })
    const res = await fetch(`${BASE}/videos?${params.toString()}`)
    if (!res.ok) throw new Error(`YouTube videos.list ${res.status}`)
    const data: any = await res.json()
    for (const it of data.items ?? []) out.set(it.id, it)
  }
  return out
}

function toItem(id: string, video: any): SourceItem {
  const sn = video?.snippet ?? {}
  return {
    id: `youtube:${id}`,
    kind: 'youtube',
    nativeId: id,
    url: `https://www.youtube.com/watch?v=${id}`,
    title: sn.title ?? '',
    uploader: sn.channelTitle,
    channelId: sn.channelId,
    durationSec: video?.contentDetails?.duration
      ? parseISODuration(video.contentDetails.duration)
      : undefined,
    views: video?.statistics?.viewCount ? Number(video.statistics.viewCount) : undefined,
    publishedAt: sn.publishedAt,
    thumbnail: sn.thumbnails?.medium?.url,
    description: sn.description,
    tags: sn.tags,
    raw: video,
  }
}

/** Una `search.list`: 100 unidades, 50 resultados (cuesta igual que pedir 20). */
/**
 * Ids para una query.
 *
 * Primero el backend con yt-dlp, que no gasta quota: con el fan-out de 3 lanes,
 * una búsqueda pasa de 303 unidades a 3 (solo los `videos.list`). Si el backend
 * no está levantado se cae a `search.list`, que anda por CORS desde el browser
 * pero cuesta 100 unidades por query.
 */
async function buscarIds(q: string): Promise<string[]> {
  try {
    return await discoverIds(q, MAX_RESULTS_POR_BUSQUEDA)
  } catch {
    return buscarIdsConQuota(q)
  }
}

async function buscarIdsConQuota(q: string): Promise<string[]> {
  const params = new URLSearchParams({
    part: 'snippet',
    q,
    type: 'video',
    maxResults: String(MAX_RESULTS_POR_BUSQUEDA),
    key: KEY,
  })
  const res = await fetch(`${BASE}/search?${params.toString()}`)
  if (!res.ok) throw new Error(`YouTube search ${res.status}`)
  const data: any = await res.json()
  return (data.items ?? []).map((i: any) => i.id?.videoId).filter(Boolean)
}

export interface OpcionesDeBusqueda {
  /** cuántos candidatos devolver. Default 48. */
  limit?: number
  /** cuántas `search.list` gastar (100 unidades c/u). Default 3. */
  presupuesto?: number
  /** semilla de la rotación de sellos/artistas/años; por defecto rota por día */
  semilla?: number
  /** para medir: se llama con el plan y con lo que se descartó */
  onPlan?: (plan: PlanDeDigging) => void
}

/**
 * Descubrimiento en YouTube: abanico de queries → dedupe → stats → anti-basura
 * → orden de digging.
 *
 * El costo está acotado por el plan: N `search.list` (100 unidades c/u) más un
 * `videos.list` cada 50 ids (1 unidad). Con el presupuesto por defecto son
 * **303 unidades**, o sea ~33 búsquedas por día. Es 3× la búsqueda vieja, pero
 * por candidato es más barato (~2 unidades contra ~5) y, sobre todo, los
 * candidatos son otros: ver la tabla medida en `core/queries.ts`.
 */
export async function buscarEnYoutube(
  query: SearchQuery,
  opts: OpcionesDeBusqueda = {},
): Promise<SourceItem[]> {
  if (!KEY) throw new Error('Falta VITE_YOUTUBE_API_KEY')

  const plan = planificarQueries(query, {
    presupuesto: opts.presupuesto ?? PRESUPUESTO_POR_DEFECTO,
    semilla: opts.semilla,
  })
  opts.onPlan?.(plan)

  // En paralelo: una query que falle (quota, 400 por comillas raras) no puede
  // tumbar la búsqueda entera.
  const tandas = await Promise.allSettled(plan.queries.map((dq: DiggerQuery) => buscarIds(dq.q)))

  // Dedupe conservando la lane que lo encontró primero. Que un video aparezca
  // en varias lanes no lo hace mejor: suele ser el más obvio de la escena.
  const laneDe = new Map<string, CandidatoDeDigging['lane']>()
  for (const [i, r] of tandas.entries()) {
    if (r.status !== 'fulfilled') continue
    for (const id of r.value) if (!laneDe.has(id)) laneDe.set(id, plan.queries[i].lane)
  }
  if (!laneDe.size) return []

  const stats = await fetchStats([...laneDe.keys()])
  const candidatos: CandidatoDeDigging[] = []
  for (const [id, lane] of laneDe) {
    const video = stats.get(id)
    if (!video) continue // borrado o privado
    const item = toItem(id, video)
    if (esBasura(item)) continue
    candidatos.push({ item, lane })
  }

  // El vocabulario de la escena sirve dos veces: para armar las queries y para
  // reconocer, al volver, qué resultado es de la escena y cuál se coló.
  const escenas = ESCENAS.filter((e) => plan.escenas.includes(e.id))
  const ordenados = ordenarParaDigging(candidatos, {
    obvios: obviosDe(escenas),
    anio: plan.anio,
    pertinentes: escenas.flatMap((e) => [
      ...e.gatillos,
      ...e.populares,
      ...e.jerga,
      ...e.sellos,
      ...e.artistas,
      ...(e.nativo?.terminos ?? []),
    ]),
  })
  return ordenados.slice(0, opts.limit ?? CANDIDATOS_POR_BUSQUEDA)
}

export const youtube: DiscoverySource = {
  kind: 'youtube',
  search: (query, opts) => buscarEnYoutube(query, { limit: opts?.limit }),
}

// ---------- import de playlists propias ----------

/**
 * Saca el playlistId de una URL de YouTube, o devuelve la entrada si ya es un ID.
 * Acepta `?list=`, la forma /playlist?list= y el ID pelado.
 */
export function parsePlaylistId(input: string): string | null {
  const trimmed = input.trim()
  if (!trimmed) return null

  const fromUrl = trimmed.match(/[?&]list=([A-Za-z0-9_-]+)/)
  if (fromUrl) return fromUrl[1]

  // un ID suelto: prefijos conocidos (PL/UU/LL/FL/OL) o el mix de "watch later"
  return /^[A-Za-z0-9_-]{12,}$/.test(trimmed) ? trimmed : null
}

export interface PlaylistFetch {
  /** título tal cual está en YouTube; se usa como tag */
  title: string
  items: SourceItem[]
}

/** "JAPANESE CITY POP SAMPLES" → "japanese city pop". El sufijo no aporta nada. */
export function playlistTag(title: string): string {
  const stripped = title.replace(/\bsamples?\b/gi, '').replace(/\s{2,}/g, ' ').trim()
  return (stripped || title).toLowerCase()
}

/**
 * Trae todos los videos de una playlist como SourceItems, más su título.
 *
 * playlistItems.list cuesta 1 unidad contra las 100 de search.list, así que una
 * playlist de 500 temas sale ~20 unidades entre paginado y stats. Es de lejos la
 * forma más barata de sembrar el índice: son discos que ya elegiste a mano.
 */
export async function fetchPlaylist(playlistId: string): Promise<PlaylistFetch> {
  if (!KEY) throw new Error('Falta VITE_YOUTUBE_API_KEY')

  const metaRes = await fetch(
    `${BASE}/playlists?part=snippet&id=${playlistId}&key=${KEY}`,
  )
  if (!metaRes.ok) throw new Error(`YouTube playlists ${metaRes.status}`)
  const meta: any = await metaRes.json()
  const title: string = meta.items?.[0]?.snippet?.title ?? playlistId

  const ids: string[] = []
  let pageToken: string | undefined

  do {
    const params = new URLSearchParams({
      part: 'contentDetails',
      playlistId,
      maxResults: '50',
      key: KEY,
    })
    if (pageToken) params.set('pageToken', pageToken)

    const res = await fetch(`${BASE}/playlistItems?${params.toString()}`)
    if (!res.ok) {
      const detail = res.status === 404 ? ' (¿la playlist es privada?)' : ''
      throw new Error(`YouTube playlistItems ${res.status}${detail}`)
    }
    const data: any = await res.json()
    for (const it of data.items ?? []) {
      const id = it.contentDetails?.videoId
      if (id) ids.push(id)
    }
    pageToken = data.nextPageToken
  } while (pageToken)

  const stats = await fetchStats(ids)
  // los borrados/privados quedan sin stats: no sirven como entidad
  const items = ids.filter((id) => stats.has(id)).map((id) => toItem(id, stats.get(id)))
  return { title, items }
}

// ---------- minería de canales ----------

/**
 * Los uploads de un canal viven en una playlist implícita cuyo id es el del canal
 * con "UC" cambiado por "UU". Traerla cuesta 1 unidad cada 50 videos, contra las
 * 100 que cuesta UNA búsqueda: es ~200 veces más barato por tema.
 *
 * Es el mejor vector de descubrimiento que tenemos. Un canal del que ya guardaste
 * varios temas es un curador humano que hizo el digging por vos, y su catálogo
 * entero está sobre tu tesis.
 */
export async function fetchChannelUploads(channelId: string, max = 100): Promise<SourceItem[]> {
  if (!KEY) throw new Error('Falta VITE_YOUTUBE_API_KEY')
  if (!channelId.startsWith('UC')) throw new Error(`channelId inesperado: ${channelId}`)

  const uploads = `UU${channelId.slice(2)}`
  const ids: string[] = []
  let pageToken: string | undefined

  do {
    const params = new URLSearchParams({
      part: 'contentDetails',
      playlistId: uploads,
      maxResults: '50',
      key: KEY,
    })
    if (pageToken) params.set('pageToken', pageToken)
    const res = await fetch(`${BASE}/playlistItems?${params.toString()}`)
    if (!res.ok) throw new Error(`YouTube uploads ${res.status}`)
    const data: any = await res.json()
    for (const it of data.items ?? []) {
      const id = it.contentDetails?.videoId
      if (id) ids.push(id)
    }
    pageToken = data.nextPageToken
  } while (pageToken && ids.length < max)

  const stats = await fetchStats(ids.slice(0, max))
  return ids
    .slice(0, max)
    .filter((id) => stats.has(id))
    .map((id) => toItem(id, stats.get(id)))
}
