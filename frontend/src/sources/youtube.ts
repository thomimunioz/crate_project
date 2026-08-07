/**
 * YouTube Data API v3 — la fuente de descubrimiento principal.
 * CORS OK desde el browser con API key. Cuidar la quota: search.list = 100 unidades.
 * Ver docs/SOURCES.md
 */
import type { SourceItem, SearchQuery } from '@/core/entities'
import type { DiscoverySource } from './types'

const KEY = import.meta.env.VITE_YOUTUBE_API_KEY
const BASE = 'https://www.googleapis.com/youtube/v3'

/** Arma el string de búsqueda inyectando bias de digging (género/instrumentos). crate-scout lo mejora. */
function buildQuery(q: SearchQuery): string {
  const extra: string[] = []
  if (q.genres?.length) extra.push(q.genres.join(' '))
  if (q.instruments?.length) extra.push(q.instruments.join(' '))
  return [q.text, ...extra].filter(Boolean).join(' ').trim()
}

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
    raw: video,
  }
}

export const youtube: DiscoverySource = {
  kind: 'youtube',
  async search(query, opts) {
    if (!KEY) throw new Error('Falta VITE_YOUTUBE_API_KEY')
    const limit = opts?.limit ?? 20
    // TODO(F1): explorar order=date/relevance, filtros y paginación con criterio de quota.
    const params = new URLSearchParams({
      part: 'snippet',
      q: buildQuery(query),
      type: 'video',
      maxResults: String(limit),
      key: KEY,
    })
    const res = await fetch(`${BASE}/search?${params.toString()}`)
    if (!res.ok) throw new Error(`YouTube search ${res.status}`)
    const data: any = await res.json()
    const ids: string[] = (data.items ?? [])
      .map((i: any) => i.id?.videoId)
      .filter(Boolean)
    const stats = await fetchStats(ids)
    return ids.map((id) => toItem(id, stats.get(id)))
  },
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

/**
 * Trae todos los videos de una playlist como SourceItems.
 *
 * playlistItems.list cuesta 1 unidad contra las 100 de search.list, así que una
 * playlist de 500 temas sale ~20 unidades entre paginado y stats. Es de lejos la
 * forma más barata de sembrar el índice: son discos que ya elegiste a mano.
 */
export async function fetchPlaylist(playlistId: string): Promise<SourceItem[]> {
  if (!KEY) throw new Error('Falta VITE_YOUTUBE_API_KEY')

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
  return ids.filter((id) => stats.has(id)).map((id) => toItem(id, stats.get(id)))
}
