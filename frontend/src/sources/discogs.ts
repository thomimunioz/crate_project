/**
 * Discogs — enrichment (NO discovery). El catálogo de discos del mundo:
 * año, sello, país, género/estilo, RAREZA (want/have) y CRÉDITOS POR INSTRUMENTO.
 * Va por el proxy del backend, que además le inyecta la auth: el consumer
 * key/secret vive en el backend y nunca llega al bundle. Ver docs/SOURCES.md
 */
import type { Credit } from '@/core/entities'
import type { CatalogCandidate, CatalogRelease } from './types'
import { proxyGet } from '@/api/backend'
import { cached, WEEK_MS } from '@/db/cache'
import { createLimiter } from './throttle'

const API = 'https://api.discogs.com'

/** ~60 req/min autenticado. Search y release comparten el mismo límite. */
const limit = createLimiter(1_100)

/**
 * Búsqueda estructurada por artista + título del disco.
 *
 * Es la forma correcta de pedirle a Discogs, que indexa RELEASES: una vez que
 * MusicBrainz identificó en qué disco vive la grabación, buscamos ese disco.
 * El `q=` libre de abajo queda solo como red de contención.
 */
export async function searchRelease(
  artist: string,
  releaseTitle: string,
): Promise<CatalogCandidate[]> {
  const key = `discogs:rel:${artist}|${releaseTitle}`.toLowerCase()
  return cached(key, WEEK_MS, async () => {
    const params = new URLSearchParams({
      artist,
      release_title: releaseTitle,
      type: 'release',
      per_page: '10',
    })
    const data = await limit(() => proxyGet<any>(`${API}/database/search?${params}`))
    return (data.results ?? []).map(toCandidate)
  })
}

/** Busca releases candidatos por texto libre. Fallback cuando MusicBrainz no identifica. */
export async function searchReleases(artist: string, title: string): Promise<CatalogCandidate[]> {
  return cached(`discogs:search:${artist}|${title}`.toLowerCase(), WEEK_MS, async () => {
    const q = encodeURIComponent(`${artist} ${title}`.trim())
    const url = `${API}/database/search?q=${q}&type=release&per_page=10`
    const data = await limit(() => proxyGet<any>(url))
    return (data.results ?? []).map(toCandidate)
  })
}

/** Discogs devuelve el título como "Artista - Disco"; lo partimos para comparar por campo. */
function toCandidate(r: any): CatalogCandidate {
  const [ra, rt] = String(r.title ?? '').split(' - ')
  return {
    discogsId: r.id,
    artist: (ra ?? '').trim(),
    title: (rt ?? r.title ?? '').trim(),
    year: r.year ? Number(r.year) : undefined,
    matchText: r.title ?? '',
  }
}

/** Trae el release completo: créditos (instrumentos), género/estilo, país, want/have. */
export async function getRelease(discogsId: number): Promise<CatalogRelease> {
  return cached(`discogs:release:${discogsId}`, WEEK_MS, () => fetchRelease(discogsId))
}

async function fetchRelease(discogsId: number): Promise<CatalogRelease> {
  const data = await limit(() => proxyGet<any>(`${API}/releases/${discogsId}`))
  const credits: Credit[] = (data.extraartists ?? []).map((a: any): Credit => ({
    name: a.name,
    role: a.role,
    instrument: normalizeRole(a.role),
  }))
  return {
    discogsId,
    artist: (data.artists ?? []).map((a: any) => a.name).join(', ') || 'Unknown',
    title: data.title,
    year: data.year || undefined,
    label: data.labels?.[0]?.name,
    country: data.country,
    genres: data.genres ?? [],
    styles: data.styles ?? [],
    credits,
    want: data.community?.want,
    have: data.community?.have,
  }
}

/** Traduce el "role" de Discogs a un instrumento del taxonomy cuando aplica. */
function normalizeRole(role: string): string | undefined {
  const r = role.toLowerCase()
  const map: Record<string, string> = {
    'electric piano': 'Rhodes',
    rhodes: 'Rhodes',
    wurlitzer: 'Wurlitzer',
    piano: 'piano',
    organ: 'organ',
    guitar: 'guitar',
    bass: 'bass',
    drums: 'drums',
    strings: 'strings',
    flute: 'flute',
    saxophone: 'saxophone',
    trumpet: 'trumpet',
    vibraphone: 'vibraphone',
    vocals: 'vocals',
  }
  for (const key of Object.keys(map)) if (r.includes(key)) return map[key]
  return undefined
}
