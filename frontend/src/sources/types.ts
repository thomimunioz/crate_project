import type { SourceItem, SearchQuery, Credit } from '@/core/entities'

/** Opciones comunes a toda fuente de descubrimiento. */
export interface DiscoveryOptions {
  limit?: number
  /** la fuente avisa si respondió degradada (sin key, quota agotada): qué se perdió, no qué se rompió */
  onAviso?: (aviso: string) => void
}

/** Fuente de descubrimiento: dado un query, devuelve items crudos. */
export interface DiscoverySource {
  kind: SourceItem['kind']
  search(query: SearchQuery, opts?: DiscoveryOptions): Promise<SourceItem[]>
}

/** Candidato de catálogo para el fuzzy match (liviano). */
export interface CatalogCandidate {
  discogsId: number
  artist: string
  title: string
  year?: number
  /** texto para comparar en el fuzzy: `${artist} ${title}` */
  matchText: string
}

/** Release completo de Discogs (para enrichment). */
export interface CatalogRelease {
  discogsId: number
  artist: string
  title: string
  year?: number
  label?: string
  country?: string
  genres: string[]
  styles: string[]
  credits: Credit[]
  want?: number
  have?: number
}
