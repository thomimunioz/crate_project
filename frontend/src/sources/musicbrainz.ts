/**
 * MusicBrainz — el PRIMER salto de identificación.
 *
 * Es la única fuente que busca a nivel GRABACIÓN, que es el nivel en el que
 * vive un título de YouTube. Discogs busca releases (álbumes), así que pedirle
 * "Breve vita, non felice" —un corte dentro de un OST— no puede funcionar.
 * Medido sobre playlists reales: MB 33% con matches correctos, Discogs 14%.
 * Ver docs/SOURCES.md
 */
import { proxyGet } from '@/api/backend'
import { cached, WEEK_MS } from '@/db/cache'
import { similarity } from '@/core/fuzzy'
import { createLimiter } from './throttle'

const WS = 'https://musicbrainz.org/ws/2'

/** 1 req/seg estricto: pasarse devuelve 503. El User-Agent lo pone el proxy. */
const limit = createLimiter(1_100)

/** MB puntúa 0..100 qué tan bien pegó el query. Abajo de esto es ruido. */
const MIN_MB_SCORE = 85
/** El artista del título tiene que coincidir con el que dice MB. */
const MIN_ARTIST_SIM = 0.62

export interface MbRecording {
  recordingMbid: string
  releaseMbid?: string
  /** nombre canónico según MB, más limpio que el del título de YouTube */
  artist: string
  title: string
  /** el release donde aparece: es lo que después busca Discogs */
  releaseTitle?: string
  year?: number
  /** 0..1 — cuánta confianza tenemos en esta identificación */
  confidence: number
}

function lucene(s: string): string {
  return s.replace(/["\\]/g, ' ').trim()
}

function yearOf(rec: any): number | undefined {
  const raw = rec['first-release-date'] ?? rec.releases?.[0]?.date
  const m = String(raw ?? '').match(/^(\d{4})/)
  return m ? Number(m[1]) : undefined
}

/**
 * Identifica una grabación. Si viene artista, se exige que coincida con el de MB.
 *
 * Sin artista igual se intenta —muchos uploads de digging son solo el título—
 * pero la confianza baja: hay veinte temas llamados "Rainy Day" y no tenemos
 * con qué desambiguar. Esa diferencia después define `entity.confirmed`.
 */
export async function identifyRecording(
  artist: string | undefined,
  title: string,
): Promise<MbRecording | null> {
  const key = `mb:rec:${artist ?? ''}|${title}`.toLowerCase()
  return cached(key, WEEK_MS, async () => {
    const query = artist
      ? `recording:"${lucene(title)}" AND artist:"${lucene(artist)}"`
      : `recording:"${lucene(title)}"`
    const data = await limit(() =>
      proxyGet<any>(`${WS}/recording?query=${encodeURIComponent(query)}&fmt=json&limit=5`),
    )

    for (const rec of data.recordings ?? []) {
      if ((rec.score ?? 0) < MIN_MB_SCORE) break // vienen ordenados: si cae, el resto también
      const mbArtist = rec['artist-credit']?.[0]?.name ?? ''

      let confidence: number
      if (artist) {
        const sim = similarity(artist, mbArtist)
        if (sim < MIN_ARTIST_SIM) continue // mismo título, otro artista
        confidence = Math.min(0.95, 0.6 + 0.35 * sim)
      } else {
        // sin artista no hay desambiguación posible: se acepta, pero flojo
        if (similarity(title, rec.title ?? '') < 0.9) continue
        confidence = 0.45
      }

      const release = rec.releases?.[0]
      return {
        recordingMbid: rec.id,
        releaseMbid: release?.id,
        artist: mbArtist,
        title: rec.title ?? title,
        releaseTitle: release?.title,
        year: yearOf(rec),
        confidence,
      }
    }
    return null
  })
}

/**
 * Lookup directo por MBID, cuando la descripción del video ya lo trae.
 * No hay nada que adivinar: la confianza es máxima.
 */
export async function lookupByMbid(recordingMbid: string): Promise<MbRecording | null> {
  return cached(`mb:id:${recordingMbid}`, WEEK_MS, async () => {
    const data = await limit(() =>
      proxyGet<any>(`${WS}/recording/${recordingMbid}?inc=artists+releases&fmt=json`),
    )
    if (!data?.id) return null
    const release = data.releases?.[0]
    return {
      recordingMbid: data.id,
      releaseMbid: release?.id,
      artist: data['artist-credit']?.[0]?.name ?? '',
      title: data.title ?? '',
      releaseTitle: release?.title,
      year: yearOf(data),
      confidence: 0.98,
    }
  })
}
