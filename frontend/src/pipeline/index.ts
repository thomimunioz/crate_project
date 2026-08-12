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
import { identifyAudio } from '@/api/backend'
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
/**
 * Por cada resultado de una fuente secundaria entran estos de la principal.
 *
 * No es parejo a propósito: medido sobre resultados reales, YouTube identifica
 * 72% contra catálogo e Internet Archive 1 de 9 —sus títulos casi nunca tienen
 * forma "Artista - Tema"—. Repartir mitad y mitad sería cambiar buenos
 * candidatos por malos.
 */
const CUOTA_FUENTE_PRINCIPAL = 3

export async function discover(query: SearchQuery): Promise<SourceItem[]> {
  const sources = sourcesFor(query.sources)
  const settled = await Promise.allSettled(sources.map((s) => s.search(query)))
  const porFuente = settled.map((r) => (r.status === 'fulfilled' ? r.value : []))
  return intercalar(porFuente)
}

/**
 * Intercala fuente por fuente antes del recorte de ENRICH_LIMIT.
 *
 * Antes se concatenaba, así que con YouTube devolviendo 48 candidatos el
 * `slice(0, 24)` se comía uno solo y las demás fuentes nunca llegaban a
 * enriquecerse.
 */
function intercalar(listas: SourceItem[][]): SourceItem[] {
  const [principal = [], ...resto] = listas
  const out: SourceItem[] = []
  let i = 0
  let j = 0
  while (i < principal.length || resto.some((l) => j < l.length)) {
    out.push(...principal.slice(i, i + CUOTA_FUENTE_PRINCIPAL))
    i += CUOTA_FUENTE_PRINCIPAL
    for (const lista of resto) if (lista[j]) out.push(lista[j])
    j++
  }
  return out
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
    // En Archive el `creator` suele ser el artista del disco; en YouTube es el
    // canal, que no lo es (salvo los "- Topic", que ya resuelven los hints).
    const artistaDeFuente = source.kind === 'archive' ? source.uploader : undefined
    return {
      source,
      cleanedTitle: cleanTitle(source.title),
      // lo probado le gana a lo parseado del título, y eso al dato de la fuente
      artist: hints.artist ?? artist ?? artistaDeFuente,
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
  /**
   * Cuánto pesa el artista. Se baja cuando la obra ya está identificada por otra
   * vía: ahí lo único que falta es encontrar EL DISCO, y comparar nombres de
   * artista entre alfabetos distintos solo mete ruido — similarity('山下達郎',
   * 'Tatsuro Yamashita') da 0 aunque sean la misma persona.
   */
  pesoArtista = 0.5,
): Promise<{ release: CatalogRelease; score: number } | null> {
  let best: { item: CatalogCandidate; score: number } | null = null
  for (const cand of candidates) {
    const score =
      pesoArtista * similarity(expectArtist, cand.artist) +
      (1 - pesoArtista) * similarity(expectRelease, cand.title)
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
      // si sabemos el disco, se busca por disco: el título del tema no lo encuentra
      const free = await discogs.searchReleases(artistHint, albumHint ?? rawTitle)
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

/** Abajo de esto la huella no alcanza para pisar lo que ya sabíamos. */
const MIN_HUELLA = 0.5

/**
 * Identifica un track por HUELLA ACÚSTICA y lo vuelve a enriquecer.
 *
 * Es el desempate para lo que el texto no puede leer: kanji, cirílico, títulos
 * sueltos de una palabra. Una vez que la huella dice qué obra es, Discogs
 * enriquece igual que siempre — mismo segundo salto, otro primer salto.
 */
export async function identifyByFingerprint(
  track: EnrichedTrack,
  query: SearchQuery,
  affinity: Affinity,
): Promise<EnrichedTrack> {
  const src = track.sources[0]
  if (!src) throw new Error('el track no tiene fuente para analizar')

  const { candidates } = await identifyAudio(src.url)
  const mejor = candidates.find((c) => c.recording_mbid && c.confidence >= MIN_HUELLA)
  if (!mejor) throw new Error('la huella no encontró la grabación en AcoustID')

  const artist = mejor.artist ?? track.entity.artist

  // AcoustID devuelve todos los discos donde aparece la grabación, y el primero
  // suele ser un box set o un recopilatorio. Se prueban varios, empezando por
  // los títulos más cortos: el álbum original casi siempre se llama más simple
  // que "The RCA/Air Years LP Box 1976–1982".
  const albumes = [...new Set(mejor.releases)]
    .sort((a, b) => a.length - b.length)
    .slice(0, 3)

  let matched: { release: CatalogRelease; score: number } | null = null
  for (const album of albumes) {
    if (!artist) break
    try {
      // El `artist=` estructurado de Discogs no matchea nombres en kanji; el `q=`
      // libre sí. Y como la grabación ya está identificada por la huella, lo único
      // que falta es dar con el disco: el artista pesa poco.
      const candidatos = [
        ...(await discogs.searchRelease(artist, album)),
        ...(await discogs.searchReleases(artist, album)),
      ]
      matched = await pickRelease(candidatos, artist, album, 0.75, 0.15)
      if (matched) break
    } catch {
      /* Discogs falló para este disco: se prueba el siguiente */
    }
  }

  const rel = matched?.release
  const entity: MusicEntity = {
    ...track.entity,
    crateId: `mb:${mejor.recording_mbid}`,
    artist,
    title: mejor.title ?? track.entity.title,
    year: rel?.year ?? track.entity.year,
    label: rel?.label ?? track.entity.label,
    country: rel?.country ?? track.entity.country,
    genres: rel?.genres ?? track.entity.genres,
    styles: rel?.styles ?? track.entity.styles,
    credits: rel?.credits ?? track.entity.credits,
    discogsId: rel?.discogsId ?? track.entity.discogsId,
    recordingMbid: mejor.recording_mbid ?? undefined,
    confirmed: true,
    identifiedBy: 'acoustid',
  }

  const fromCredits = entity.credits
    .map((cr) => cr.instrument)
    .filter((x): x is string => Boolean(x))

  const identificado: EnrichedTrack = {
    ...track,
    crateId: entity.crateId,
    entity,
    instruments: fromCredits.length
      ? confirmedProv(Array.from(new Set(fromCredits)), 'discogs')
      : track.instruments,
    rarity: {
      ...track.rarity,
      discogsWant: rel?.want ?? track.rarity.discogsWant,
      discogsHave: rel?.have ?? track.rarity.discogsHave,
    },
    pending: false,
    updatedAt: new Date().toISOString(),
  }
  return scoreAll([identificado], query, affinity)[0]
}
