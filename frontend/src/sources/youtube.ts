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

async function fetchStats(ids: string[]): Promise<Map<string, any>> {
  const out = new Map<string, any>()
  if (ids.length === 0) return out
  // videos.list = 1 unidad; barato. Trae stats + duración.
  const params = new URLSearchParams({
    part: 'statistics,contentDetails,snippet',
    id: ids.join(','),
    key: KEY,
  })
  const res = await fetch(`${BASE}/videos?${params.toString()}`)
  if (!res.ok) throw new Error(`YouTube videos.list ${res.status}`)
  const data: any = await res.json()
  for (const it of data.items ?? []) out.set(it.id, it)
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
