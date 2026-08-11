/**
 * Pistas duras que YouTube ya nos da y no estábamos leyendo.
 *
 * El `snippet` de `videos.list` viene con descripción, tags y canal, y eso ya lo
 * pagamos: es la misma llamada de 1 unidad que hacemos para traer las views.
 * Medido sobre las playlists del usuario, entre un tercio y la mitad de los temas
 * traen identificación EXACTA ahí adentro — sin fuzzy, sin umbrales:
 *
 *   canal "MINAKO YOSHIDA - Topic" + descripción
 *     "RAINY DAY · Minako Yoshida / MONOCHROME / ℗ 1980 ALFA MUSIC"
 *   descripción con "https://www.discogs.com/release/8195268"
 *
 * Ese mismo tema, adivinado desde el título "RAINY DAY", cruzaba con una banda de
 * ska. Preferimos probar antes que adivinar. Ver docs/SOURCES.md
 */

/** De dónde salió la pista. Ordenado de más a menos confiable. */
export type HintSource = 'catalog_link' | 'topic_channel' | 'labeled_fields' | 'none'

export interface YtHints {
  artist?: string
  title?: string
  album?: string
  year?: number
  label?: string
  discogsReleaseId?: number
  discogsMasterId?: number
  recordingMbid?: string
  releaseMbid?: string
  /**
   * Nombres alternativos sacados de los tags: el mismo artista en romaji, kanji y
   * katakana. No afirmamos cuál es el artista, pero sirven para reintentar el
   * match con el nombre que use cada catálogo.
   */
  aliases: string[]
  source: HintSource
  /** 0..1 — qué tan fuerte es la evidencia, no qué tan completa */
  confidence: number
}

export const NO_HINTS: YtHints = { aliases: [], source: 'none', confidence: 0 }

// ---------- links directos a catálogo ----------

// acepta el prefijo de idioma: /es/release/123, /release/123-Nombre-Del-Disco
const DISCOGS_RELEASE = /discogs\.com\/(?:[a-z]{2}\/)?release\/(\d+)/i
const DISCOGS_MASTER = /discogs\.com\/(?:[a-z]{2}\/)?master\/(\d+)/i
const MB_RECORDING = /musicbrainz\.org\/recording\/([0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12})/i
const MB_RELEASE = /musicbrainz\.org\/release\/([0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12})/i

// ---------- canales "- Topic" ----------

/**
 * YouTube genera los canales "- Topic" desde el feed de las discográficas, así que
 * la descripción tiene siempre la misma forma:
 *
 *   Provided to YouTube by <distribuidora>
 *   <tema> · <artista> [· <artista2>…]
 *   <disco>
 *   ℗ <año> <sello>
 */
const TOPIC_CHANNEL = /\s-\sTopic$/
const PROVIDED_BY = /^Provided to YouTube by\s+(.+)$/im
const PHONOGRAM = /℗\s*(\d{4})\s*(.*)$/m

// ---------- campos etiquetados a mano ----------

const FIELD = (name: string): RegExp => new RegExp(`^\s*${name}\s*:\s*(.+)$`, 'im')

const clean = (s: string | undefined): string | undefined => {
  const t = s?.trim().replace(/\s{2,}/g, ' ')
  return t || undefined
}

function toYear(raw: string | undefined): number | undefined {
  const m = raw?.match(/\b(19[2-9]\d|20[0-2]\d)\b/)
  return m ? Number(m[1]) : undefined
}

/** Parsea el bloque de un canal "- Topic". Devuelve null si no tiene esa forma. */
function parseTopic(channelTitle: string, description: string): Partial<YtHints> | null {
  if (!TOPIC_CHANNEL.test(channelTitle) && !PROVIDED_BY.test(description)) return null

  const lines = description
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)

  // la línea "tema · artista" es la primera con separador de punto medio
  const i = lines.findIndex((l) => l.includes(' · '))
  if (i === -1) return null

  const [rawTitle, ...artists] = lines[i].split(' · ').map((p) => p.trim())
  const phono = description.match(PHONOGRAM)

  return {
    title: clean(rawTitle),
    // varios artistas: el primero es el principal, el resto son intérpretes
    artist: clean(artists[0]) ?? clean(channelTitle.replace(TOPIC_CHANNEL, '')),
    // la línea siguiente al bloque de artistas es el disco
    album: clean(lines[i + 1]),
    year: toYear(phono?.[1]),
    label: clean(phono?.[2]),
  }
}

/** Campos escritos a mano por el uploader: "Album: X", "Year: 1986". */
function parseFields(description: string): Partial<YtHints> {
  const grab = (name: string): string | undefined => clean(description.match(FIELD(name))?.[1])
  return {
    album: grab('album'),
    year: toYear(grab('year') ?? grab('año')),
    label: grab('label') ?? grab('sello'),
    artist: grab('artist') ?? grab('artista'),
  }
}

/**
 * Extrae todo lo que se pueda probar del snippet de YouTube.
 * No inventa: si no hay evidencia, devuelve `NO_HINTS`.
 */
export function extractHints(input: {
  channelTitle?: string
  description?: string
  tags?: string[]
}): YtHints {
  const desc = input.description ?? ''
  const channel = input.channelTitle ?? ''
  const aliases = (input.tags ?? []).map((t) => t.trim()).filter(Boolean)

  const discogsRelease = desc.match(DISCOGS_RELEASE)?.[1]
  const discogsMaster = desc.match(DISCOGS_MASTER)?.[1]
  const mbRecording = desc.match(MB_RECORDING)?.[1]
  const mbRelease = desc.match(MB_RELEASE)?.[1]

  const topic = parseTopic(channel, desc)
  const fields = parseFields(desc)

  // el link a catálogo es la evidencia más fuerte: es un id, no una interpretación
  const hasLink = Boolean(discogsRelease || discogsMaster || mbRecording || mbRelease)
  const source: HintSource = hasLink
    ? 'catalog_link'
    : topic
      ? 'topic_channel'
      : fields.album || fields.artist
        ? 'labeled_fields'
        : 'none'

  if (source === 'none') return { ...NO_HINTS, aliases }

  const merged = { ...fields, ...stripUndefined(topic ?? {}) }
  return {
    ...merged,
    discogsReleaseId: discogsRelease ? Number(discogsRelease) : undefined,
    discogsMasterId: discogsMaster ? Number(discogsMaster) : undefined,
    recordingMbid: mbRecording?.toLowerCase(),
    releaseMbid: mbRelease?.toLowerCase(),
    aliases,
    source,
    confidence: source === 'catalog_link' ? 0.95 : source === 'topic_channel' ? 0.9 : 0.7,
  }
}

/** Quita las claves en undefined para que no pisen valores buenos al hacer spread. */
function stripUndefined<T extends object>(o: T): Partial<T> {
  return Object.fromEntries(Object.entries(o).filter(([, v]) => v !== undefined)) as Partial<T>
}
