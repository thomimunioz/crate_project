/**
 * MusicBrainz — IDs canónicos (MBID) para desambiguar/cruzar entidades.
 * Rate limit ESTRICTO (1 req/seg) + User-Agent → va por el proxy con throttling.
 * Ver docs/SOURCES.md
 */
import { proxyGet } from '@/api/backend'

const WS = 'https://musicbrainz.org/ws/2'

export interface MbMatch {
  recordingMbid?: string
  releaseMbid?: string
  score: number
}

/** Busca una grabación por artista + título. Devuelve el mejor MBID si hay match razonable. */
export async function lookupRecording(artist: string, title: string): Promise<MbMatch | null> {
  const q = encodeURIComponent(`artist:"${artist}" AND recording:"${title}"`)
  // TODO(F1): throttlear a 1 req/seg en el proxy; cachear por (artist,title).
  const data = await proxyGet<any>(`${WS}/recording?query=${q}&fmt=json&limit=3`)
  const rec = data.recordings?.[0]
  if (!rec) return null
  return {
    recordingMbid: rec.id,
    releaseMbid: rec.releases?.[0]?.id,
    score: typeof rec.score === 'number' ? rec.score / 100 : 0.5,
  }
}
