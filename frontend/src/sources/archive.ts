/**
 * Internet Archive — discos viejos digitalizados, legal. advancedsearch.php es CORS-friendly.
 * Ver docs/SOURCES.md
 */
import type { SourceItem, SearchQuery } from '@/core/entities'
import type { DiscoverySource } from './types'

const BASE = 'https://archive.org/advancedsearch.php'

/** Colecciones con material de digging real, para no traer podcasts ni charlas. */
const COLECCIONES = ['audio_music', 'etree', '78rpm']

function buildQuery(q: SearchQuery): string {
  const partes = [`(${q.text})`, 'mediatype:(audio)']
  if (q.genres?.length) partes.push(`(${q.genres.join(' OR ')})`)
  if (q.year) partes.push(`year:[${q.year[0]} TO ${q.year[1]}]`)
  partes.push(`collection:(${COLECCIONES.join(' OR ')})`)
  return partes.join(' AND ')
}

export const archive: DiscoverySource = {
  kind: 'archive',
  async search(query, opts) {
    const limit = opts?.limit ?? 20
    const params = new URLSearchParams({ q: buildQuery(query), rows: String(limit), output: 'json' })
    for (const fl of ['identifier', 'title', 'creator', 'year', 'downloads']) {
      params.append('fl[]', fl)
    }
    const res = await fetch(`${BASE}?${params.toString()}`)
    if (!res.ok) throw new Error(`Archive search ${res.status}`)
    const data: any = await res.json()
    const docs: any[] = data?.response?.docs ?? []
    return docs.map((d): SourceItem => {
      const creator = Array.isArray(d.creator) ? d.creator[0] : d.creator
      return {
        id: `archive:${d.identifier}`,
        kind: 'archive',
        nativeId: d.identifier,
        url: `https://archive.org/details/${d.identifier}`,
        // OJO: `creator` en Archive suele ser QUIEN SUBIÓ la colección, no el
        // artista. Anteponerlo al título hacía que el split tomara al uploader
        // como artista ("Blinkky.fr") y no cruzaba nada contra catálogo.
        title: d.title || d.identifier,
        uploader: creator,
        views: d.downloads ? Number(d.downloads) : undefined,
        publishedAt: d.year ? `${d.year}-01-01` : undefined,
        raw: d,
      }
    })
  },
}
