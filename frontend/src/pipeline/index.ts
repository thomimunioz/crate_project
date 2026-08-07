/**
 * Pipeline de la Capa 1 (metadata-first, en el browser):
 *   discover → normalize → enrich → score
 * Ver docs/ARCHITECTURE.md
 */
import type {
  SourceItem,
  Candidate,
  EnrichedTrack,
  MusicEntity,
  SearchQuery,
} from '@/core/entities'
import type { Affinity } from '@/core/affinity'
import { splitArtistTitle, extractYear, cleanTitle, bestMatch } from '@/core/fuzzy'
import { computeCrateScore } from '@/core/score'
import { inferMoodFromText, instrumentsFromText } from '@/core/taxonomy'
import { confirmed, inferred } from '@/core/provenance'
import { sourcesFor, discogs, musicbrainz } from '@/sources'

/**
 * Cuántos candidatos se enriquecen por búsqueda.
 *
 * El enrichment está serializado por fuente (ver sources/throttle.ts), así que
 * cada candidato cuesta ~1.1s de Discogs en frío. No se baja el número: enriquecer
 * menos es tener menos resultados con créditos y rareza, que es lo que alimenta el
 * score. El cache (db/cache.ts) hace que la segunda pasada sea instantánea.
 */
const ENRICH_LIMIT = 24

// ---------- discover ----------
export async function discover(query: SearchQuery): Promise<SourceItem[]> {
  const sources = sourcesFor(query.sources)
  const settled = await Promise.allSettled(sources.map((s) => s.search(query)))
  return settled.flatMap((r) => (r.status === 'fulfilled' ? r.value : []))
}

// ---------- normalize ----------
function parseBpm(text: string): number | undefined {
  const m = text.match(/\b(\d{2,3})\s?bpm\b/i)
  return m ? Number(m[1]) : undefined
}

function parseKey(text: string): string | undefined {
  // conservador: "Am", "F# minor", "Bb maj", "key of C"
  const m = text.match(/\b([A-G][#b]?)\s?(minor|major|min|maj|m)\b/)
  if (m) {
    const mode = /maj/i.test(m[2]) ? ' major' : ' minor'
    return `${m[1]}${m[2].toLowerCase() === 'm' || /min/i.test(m[2]) ? ' minor' : mode}`
  }
  const k = text.match(/key of ([A-G][#b]?)/i)
  return k ? k[1] : undefined
}

export function normalize(items: SourceItem[]): Candidate[] {
  return items.map((source): Candidate => {
    const { artist, title } = splitArtistTitle(source.title)
    return {
      source,
      cleanedTitle: cleanTitle(source.title),
      artist,
      title,
      year: extractYear(source.title),
      bpm: parseBpm(source.title),
      key: parseKey(source.title),
      parseConfidence: artist ? 0.7 : 0.4,
    }
  })
}

// ---------- enrich ----------
function slug(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')
}

function daysSince(iso?: string): number | undefined {
  if (!iso) return undefined
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return undefined
  return Math.max(0, Math.round((Date.now() - then) / 86_400_000))
}

async function enrichOne(c: Candidate): Promise<EnrichedTrack> {
  const now = new Date().toISOString()
  const searchText = `${c.artist ?? ''} ${c.title ?? c.cleanedTitle}`.trim()

  // 1) cruce con Discogs (fuzzy)
  let entity: MusicEntity | null = null
  let discogsWant: number | undefined
  let discogsHave: number | undefined
  try {
    const cands = await discogs.searchReleases(c.artist ?? '', c.title ?? c.cleanedTitle)
    const match = bestMatch(
      searchText,
      cands.map((r) => ({ item: r, text: r.matchText })),
    )
    if (match) {
      const rel = await discogs.getRelease(match.item.discogsId)
      entity = {
        crateId: `discogs:${rel.discogsId}`,
        artist: rel.artist,
        title: rel.title,
        year: rel.year ?? c.year,
        label: rel.label,
        country: rel.country,
        genres: rel.genres,
        styles: rel.styles,
        credits: rel.credits,
        discogsId: rel.discogsId,
        confirmed: match.score >= 0.8,
      }
      discogsWant = rel.want
      discogsHave = rel.have
      // 2) MBIDs (opcional, solo si confirmado)
      if (entity.confirmed) {
        try {
          const mb = await musicbrainz.lookupRecording(entity.artist, entity.title)
          if (mb) {
            entity.recordingMbid = mb.recordingMbid
            entity.releaseMbid = mb.releaseMbid
          }
        } catch {
          /* MusicBrainz opcional: degradar con gracia */
        }
      }
    }
  } catch {
    /* Discogs falló: seguimos con lo que hay */
  }

  // fallback: entidad sin confirmar a partir del candidate
  if (!entity) {
    entity = {
      crateId: `guess:${slug(searchText) || c.source.nativeId}`,
      artist: c.artist ?? 'Unknown',
      title: c.title ?? c.cleanedTitle,
      year: c.year,
      genres: [],
      styles: [],
      credits: [],
      confirmed: false,
    }
  }

  // instrumentos: de créditos (catálogo) o del texto (parsed)
  const fromCredits = entity.credits
    .map((cr) => cr.instrument)
    .filter((x): x is string => Boolean(x))
  const instrumentsList = fromCredits.length
    ? confirmed(Array.from(new Set(fromCredits)), 'discogs')
    : (() => {
        const fromText = instrumentsFromText(c.source.title)
        return fromText.length ? confirmed(fromText, 'youtube_title', 0.5) : undefined
      })()

  const mood = inferred(inferMoodFromText(c.source.title, entity.genres.concat(entity.styles)), 0.55)

  return {
    crateId: entity.crateId,
    entity,
    sources: [c.source],
    bpm: c.bpm != null ? confirmed(c.bpm, 'youtube_title', 0.6) : undefined,
    key: c.key ? confirmed(c.key, 'youtube_title', 0.5) : undefined,
    mood,
    instruments: instrumentsList,
    rarity: {
      discogsWant,
      discogsHave,
      youtubeViews: c.source.kind === 'youtube' ? c.source.views : undefined,
      uploadAgeDays: daysSince(c.source.publishedAt),
    },
    status: 'seen',
    firstSeenAt: now,
    updatedAt: now,
  }
}

export async function enrich(candidates: Candidate[]): Promise<EnrichedTrack[]> {
  const slice = candidates.slice(0, ENRICH_LIMIT)
  const settled = await Promise.allSettled(slice.map(enrichOne))
  return settled.flatMap((r) => (r.status === 'fulfilled' ? [r.value] : []))
}

// ---------- score + orquestación ----------
export function scoreAll(
  tracks: EnrichedTrack[],
  query: SearchQuery,
  affinity: Affinity,
): EnrichedTrack[] {
  return tracks
    .map((t) => ({ ...t, score: computeCrateScore(t, query, affinity) }))
    .sort((a, b) => (b.score?.total ?? 0) - (a.score?.total ?? 0))
}

/** Corre el pipeline entero. La UI filtra los `seen` aparte (ver store). */
export async function runSearch(query: SearchQuery, affinity: Affinity): Promise<EnrichedTrack[]> {
  const items = await discover(query)
  const candidates = normalize(items)
  const enriched = await enrich(candidates)
  return scoreAll(enriched, query, affinity)
}
