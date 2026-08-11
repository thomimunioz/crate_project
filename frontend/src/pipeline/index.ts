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
import { splitArtistTitle, extractYear, cleanTitle, similarity } from '@/core/fuzzy'
import { extractHints } from '@/core/ytHints'
import { computeCrateScore } from '@/core/score'
import { inferMoodFromText, instrumentsFromText } from '@/core/taxonomy'
import { confirmed as confirmedProv, inferred } from '@/core/provenance'
import { sourcesFor, discogs, musicbrainz } from '@/sources'
import type { CatalogCandidate, CatalogRelease } from '@/sources'
import type { MbRecording } from '@/sources/musicbrainz'
import { fetchPlaylist, playlistTag, fetchChannelUploads } from '@/sources/youtube'

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
    const hints = extractHints({
      channelTitle: source.uploader,
      description: source.description,
      tags: source.tags,
    })
    return {
      source,
      cleanedTitle: cleanTitle(source.title),
      // lo probado le gana a lo parseado del título
      artist: hints.artist ?? artist,
      title: hints.title ?? title,
      year: hints.year ?? extractYear(source.title),
      bpm: parseBpm(source.title),
      key: parseKey(source.title),
      parseConfidence: hints.source !== 'none' ? hints.confidence : artist ? 0.7 : 0.4,
      hints,
    }
  })
}

// ---------- enrich ----------
/** título del candidato, para desambiguar tracks dentro de un mismo release */
function mb2title(c: Candidate): string {
  return c.title ?? c.cleanedTitle
}

function slug(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')
}

function daysSince(iso?: string): number | undefined {
  if (!iso) return undefined
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return undefined
  return Math.max(0, Math.round((Date.now() - then) / 86_400_000))
}

/**
 * Elige el mejor release de Discogs comparando CAMPO CONTRA CAMPO.
 *
 * Concatenar artista+título y medir Levenshtein deja que el largo del nombre
 * del artista domine: "Ennio Morricone - Debora" matcheaba "Ennio Morricone -
 * Amore" con 0.82 siendo otro tema. Ver docs/SOURCES.md
 */
async function pickRelease(
  candidates: CatalogCandidate[],
  expectArtist: string,
  expectRelease: string,
  minScore: number,
): Promise<{ release: CatalogRelease; score: number } | null> {
  let best: { item: CatalogCandidate; score: number } | null = null
  for (const cand of candidates) {
    const score =
      0.5 * similarity(expectArtist, cand.artist) + 0.5 * similarity(expectRelease, cand.title)
    if (!best || score > best.score) best = { item: cand, score }
  }
  if (!best || best.score < minScore) return null
  return { release: await discogs.getRelease(best.item.discogsId), score: best.score }
}

/**
 * Enriquece un candidato en dos saltos:
 *   1. MusicBrainz identifica la GRABACIÓN (el nivel en el que vive un título
 *      de YouTube) y devuelve artista canónico, disco y año.
 *   2. Discogs enriquece ESE disco: créditos por instrumento, sello, país y
 *      want/have, que es de donde salen instrumentos y rareza para el score.
 *
 * Si MB no identifica, se cae al cruce por texto libre contra Discogs. Si Discogs
 * falla pero MB identificó, igual queda una entidad usable: antes de esto, que
 * fallara Discogs significaba quedarse sin nada.
 */
async function enrichOne(c: Candidate): Promise<EnrichedTrack> {
  const now = new Date().toISOString()
  const rawTitle = c.title ?? c.cleanedTitle

  const hints = c.hints

  let mb: MbRecording | null = null
  try {
    mb = hints.recordingMbid
      ? await musicbrainz.lookupByMbid(hints.recordingMbid) // el video trae el MBID: no hay nada que adivinar
      : await musicbrainz.identifyRecording(c.artist, rawTitle)
  } catch {
    /* MusicBrainz opcional: degradar con gracia */
  }

  const artistHint = hints.artist ?? mb?.artist ?? c.artist
  const albumHint = hints.album ?? mb?.releaseTitle

  let matched: { release: CatalogRelease; score: number } | null = null
  try {
    // 1) el video linkea el release: una sola llamada, sin buscar ni comparar
    const directId =
      hints.discogsReleaseId ??
      (hints.discogsMasterId ? await discogs.masterMainRelease(hints.discogsMasterId) : null)
    if (directId) {
      matched = { release: await discogs.getRelease(directId), score: 1 }
    }
    // 2) sabemos artista y disco: búsqueda estructurada
    if (!matched && artistHint && albumHint) {
      matched = await pickRelease(
        await discogs.searchRelease(artistHint, albumHint),
        artistHint,
        albumHint,
        0.62,
      )
    }
    // 3) red de contención: texto libre
    if (!matched && artistHint) {
      const free = await discogs.searchReleases(artistHint, rawTitle)
      matched = await pickRelease(free, artistHint, albumHint ?? rawTitle, 0.7)
    }
  } catch {
    /* Discogs falló: seguimos con lo que haya dado MB o las pistas */
  }

  /**
   * Confirmar significa "creemos que esta es la obra real", y eso lo decide
   * QUIEN identificó. Si MusicBrainz identificó, manda su confianza: que Discogs
   * después encuentre ese disco solo prueba que los dos catálogos coinciden, no
   * que la identificación haya sido buena. Un título suelto como "Rainy Day"
   * matchea con cualquier cosa y Discogs lo corrobora prolijamente.
   * Sin MusicBrainz, el cruce directo contra Discogs tiene que ser fuerte solo.
   */
  const proven = hints.source === 'catalog_link' || hints.source === 'topic_channel'
  const confirmed = proven
    ? true
    : mb
      ? mb.confidence >= 0.7 && matched !== null
      : matched !== null && matched.score >= 0.85

  const rel = matched?.release
  const entity: MusicEntity = {
    // La identidad es del TRACK, no del disco. El MBID de grabación ya es
    // track-level; el id de Discogs es del release, así que tres cortes del
    // mismo OST colapsarían en una sola clave y se pisarían en Dexie.
    crateId: hints.recordingMbid
      ? `mb:${hints.recordingMbid}`
      : mb
      ? `mb:${mb.recordingMbid}`
      : rel
        ? `discogs:${rel.discogsId}:${slug(mb2title(c))}`
        : `guess:${slug(`${artistHint ?? ''} ${rawTitle}`) || c.source.nativeId}`,
    artist: hints.artist ?? rel?.artist ?? mb?.artist ?? c.artist ?? 'Unknown',
    title: hints.title ?? mb?.title ?? c.title ?? c.cleanedTitle,
    // el ℗ de la descripción es el año de la obra; el de Discogs puede ser de una reedición
    year: hints.year ?? rel?.year ?? mb?.year ?? c.year,
    label: rel?.label ?? hints.label,
    country: rel?.country,
    genres: rel?.genres ?? [],
    styles: rel?.styles ?? [],
    credits: rel?.credits ?? [],
    discogsId: rel?.discogsId,
    recordingMbid: mb?.recordingMbid,
    releaseMbid: mb?.releaseMbid,
    confirmed,
    identifiedBy:
      hints.source === 'catalog_link'
        ? 'catalog_link'
        : hints.source === 'topic_channel'
          ? 'topic_channel'
          : mb
            ? 'musicbrainz'
            : matched
              ? 'discogs'
              : undefined,
  }

  // instrumentos: de créditos (catálogo) o del texto (parsed)
  const fromCredits = entity.credits
    .map((cr) => cr.instrument)
    .filter((x): x is string => Boolean(x))
  const instrumentsList = fromCredits.length
    ? confirmedProv(Array.from(new Set(fromCredits)), 'discogs')
    : (() => {
        const fromText = instrumentsFromText(c.source.title)
        return fromText.length ? confirmedProv(fromText, 'youtube_title', 0.5) : undefined
      })()

  const mood = inferred(inferMoodFromText(c.source.title, entity.genres.concat(entity.styles)), 0.55)

  return {
    crateId: entity.crateId,
    entity,
    sources: [c.source],
    bpm: c.bpm != null ? confirmedProv(c.bpm, 'youtube_title', 0.6) : undefined,
    key: c.key ? confirmedProv(c.key, 'youtube_title', 0.5) : undefined,
    mood,
    instruments: instrumentsList,
    rarity: {
      discogsWant: rel?.want,
      discogsHave: rel?.have,
      youtubeViews: c.source.kind === 'youtube' ? c.source.views : undefined,
      uploadAgeDays: daysSince(c.source.publishedAt),
    },
    status: 'seen',
    firstSeenAt: now,
    updatedAt: now,
  }
}

export interface EnrichOptions {
  /** cuántos candidatos enriquecer. Por defecto ENRICH_LIMIT. */
  limit?: number
  onProgress?: (done: number, total: number) => void
  /** se llama con cada track apenas termina de cruzarse, para render progresivo */
  onTrack?: (track: EnrichedTrack) => void
}

export async function enrich(
  candidates: Candidate[],
  opts: EnrichOptions = {},
): Promise<EnrichedTrack[]> {
  const slice = candidates.slice(0, opts.limit ?? ENRICH_LIMIT)
  let done = 0
  const settled = await Promise.allSettled(
    slice.map((c) =>
      enrichOne(c)
        .then((t) => {
          opts.onTrack?.(t)
          return t
        })
        .finally(() => opts.onProgress?.(++done, slice.length)),
    ),
  )
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

/**
 * Ficha provisional con lo que YouTube ya nos dio, antes de cruzar contra catálogo.
 * El cruce tarda ~2s por tema y son decenas: mostrar esto de entrada es la
 * diferencia entre una app que responde y 60 segundos de spinner.
 */
function placeholder(c: Candidate): EnrichedTrack {
  const now = new Date().toISOString()
  return {
    crateId: `pending:${c.source.id}`,
    entity: {
      crateId: `pending:${c.source.id}`,
      artist: c.artist ?? 'Buscando…',
      title: c.title ?? c.cleanedTitle,
      year: c.year,
      genres: [],
      styles: [],
      credits: [],
      confirmed: false,
    },
    sources: [c.source],
    bpm: c.bpm != null ? confirmedProv(c.bpm, 'youtube_title', 0.6) : undefined,
    key: c.key ? confirmedProv(c.key, 'youtube_title', 0.5) : undefined,
    rarity: {
      youtubeViews: c.source.kind === 'youtube' ? c.source.views : undefined,
      uploadAgeDays: daysSince(c.source.publishedAt),
    },
    pending: true,
    status: 'seen',
    firstSeenAt: now,
    updatedAt: now,
  }
}

/**
 * Ordena dejando arriba lo ya cruzado (por score) y abajo lo que falta, en el
 * orden en que vino. Así las fichas suben a su lugar a medida que se completan,
 * en vez de barajarse toda la lista en cada llegada.
 */
function orderPartial(
  tracks: EnrichedTrack[],
  query: SearchQuery,
  affinity: Affinity,
): EnrichedTrack[] {
  const listos = tracks.filter((t) => !t.pending)
  const faltan = tracks.filter((t) => t.pending)
  return [...scoreAll(listos, query, affinity), ...faltan]
}

/**
 * Corre el pipeline entero. La UI filtra los `seen` aparte (ver store).
 * `onPartial` recibe la lista completa cada vez que una ficha se completa.
 */
export interface SearchOptions {
  onPartial?: (tracks: EnrichedTrack[]) => void
  /** ids de fuente a descartar sin enriquecer: "no me muestres lo que ya vi" */
  skipSourceIds?: Set<string>
}

export async function runSearch(
  query: SearchQuery,
  affinity: Affinity,
  opts: SearchOptions = {},
): Promise<EnrichedTrack[]> {
  return runOnItems(await discover(query), query, affinity, opts)
}

/**
 * Mina los uploads de un canal entero.
 *
 * Un canal del que ya guardaste varios temas es un curador humano que hizo el
 * digging por vos. Traerlo cuesta 1 unidad cada 50 videos contra las 100 de una
 * sola búsqueda: por tema es ~200 veces más barato. Ver docs/SOURCES.md
 */
export async function mineChannel(
  channelId: string,
  query: SearchQuery,
  affinity: Affinity,
  opts: SearchOptions = {},
): Promise<EnrichedTrack[]> {
  return runOnItems(await fetchChannelUploads(channelId), query, affinity, opts)
}

async function runOnItems(
  items: SourceItem[],
  query: SearchQuery,
  affinity: Affinity,
  opts: SearchOptions,
): Promise<EnrichedTrack[]> {
  const { onPartial, skipSourceIds } = opts
  const candidates = normalize(items)
    .filter((c) => !skipSourceIds?.has(c.source.id))
    .slice(0, ENRICH_LIMIT)

  // clave estable: el crateId cambia cuando el cruce identifica la obra
  const porFuente = new Map(candidates.map((c) => [c.source.id, placeholder(c)]))
  const emitir = (): void => onPartial?.(orderPartial([...porFuente.values()], query, affinity))
  emitir()

  const enriched = await enrich(candidates, {
    limit: candidates.length,
    onTrack: (t) => {
      porFuente.set(t.sources[0].id, t)
      emitir()
    },
  })
  return scoreAll(enriched, query, affinity)
}

/**
 * Import de una playlist propia como semilla del crate.
 *
 * Son discos que ya elegiste a mano para samplear: es la mejor señal de affinity
 * que existe, mucho mejor que los clicks de save/reject, y arranca el índice sin
 * el problema de arranque en frío. Se enriquece la playlist entera, no un slice.
 */
export async function importPlaylist(
  playlistId: string,
  onProgress?: EnrichOptions['onProgress'],
): Promise<{ tag: string; tracks: EnrichedTrack[] }> {
  const { title, items } = await fetchPlaylist(playlistId)
  const candidates = normalize(items)
  const tracks = await enrich(candidates, { limit: candidates.length, onProgress })
  return { tag: playlistTag(title), tracks }
}
