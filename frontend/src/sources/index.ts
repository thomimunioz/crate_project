/**
 * Registro de fuentes.
 * - Descubrimiento (F1): YouTube, Internet Archive.
 * - Enrichment: Discogs (créditos/rareza), MusicBrainz (MBIDs).
 * F2+: spotify, bandcamp, soundcloud, web, soulseek.
 */
import type { DiscoverySource } from './types'
import { youtube } from './youtube'
import { archive } from './archive'

export const discoverySources: DiscoverySource[] = [youtube, archive]

export function sourcesFor(kinds?: DiscoverySource['kind'][]): DiscoverySource[] {
  if (!kinds || kinds.length === 0) return discoverySources
  return discoverySources.filter((s) => kinds.includes(s.kind))
}

export { youtube, archive }
export * as discogs from './discogs'
export * as musicbrainz from './musicbrainz'
export type { DiscoverySource, CatalogCandidate, CatalogRelease } from './types'
