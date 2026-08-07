/**
 * Internet Archive — discos viejos digitalizados, legal. advancedsearch.php es CORS-friendly.
 * Ver docs/SOURCES.md
 */
import type { SourceItem } from '@/core/entities'
import type { DiscoverySource } from './types'

const BASE = 'https://archive.org/advancedsearch.php'

export const archive: DiscoverySource = {
  kind: 'archive',
  async search(query, opts) {
    const limit = opts?.limit ?? 20
    // TODO(F1): afinar el query (mediatype:audio, collection, year range) — trabajo de crate-scout.
    const q = `(${query.text}) AND mediatype:(audio)`
    const params = new URLSearchParams({ q, rows: String(limit), output: 'json' })
    for (const fl of ['identifier', 'title', 'creator', 'year', 'downloads']) {
      params.append('fl[]', fl)
    }
    const res = await fetch(`${BASE}?${params.toString()}`)
    if (!res.ok) throw new Error(`Archive search ${res.status}`)
    const data: any = await res.json()
    const docs: any[] = data?.response?.docs ?? []
    return docs.map((d): SourceItem => ({
      id: `archive:${d.identifier}`,
      kind: 'archive',
      nativeId: d.identifier,
      url: `https://archive.org/details/${d.identifier}`,
      title: [d.creator, d.title].filter(Boolean).join(' - ') || d.title || d.identifier,
      uploader: Array.isArray(d.creator) ? d.creator[0] : d.creator,
      views: d.downloads ? Number(d.downloads) : undefined,
      publishedAt: d.year ? `${d.year}-01-01` : undefined,
      raw: d,
    }))
  },
}
