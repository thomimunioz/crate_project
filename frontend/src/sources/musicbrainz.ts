/**
 * MusicBrainz — IDs canónicos (MBID) para desambiguar/cruzar entidades.
 * Rate limit ESTRICTO (1 req/seg) + User-Agent → va por el proxy con throttling.
 * Ver docs/SOURCES.md
 */
import { proxyGet } from '@/api/backend'
import { cached, WEEK_MS } from '@/db/cache'
import { createLimiter } from './throttle'

const WS = 'https://musicbrainz.org/ws/2'

/** 1 req/seg estricto: pasarse devuelve 503. El User-Agent lo pone el proxy. */
const limit = createLimiter(1_100)

export interface MbMatch {
  recordingMbid?: string
  releaseMbid?: string
  score: number
}

/** Busca una grabación por artista + título. Devuelve el mejor MBID si hay match razonable. */
export async function lookupRecording(artist: string, title: string): Promise<MbMatch | null> {
  return cached(`mb:recording:${artist}|${title}`.toLowerCase(), WEEK_MS, async () => {
    const q = encodeURIComponent(`artist:"${artist}" AND recording:"${title}"`)
    const data = await limit(() => proxyGet<any>(`${WS}/recording?query=${q}&fmt=json&limit=3`))
    const rec = data.recordings?.[0]
    if (!rec) return null
    return {
      recordingMbid: rec.id,
      releaseMbid: rec.releases?.[0]?.id,
      score: typeof rec.score === 'number' ? rec.score / 100 : 0.5,
    }
  })
}
