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
 *
 * Dos niveles de evidencia, y no se mezclan (CLAUDE.md: provenance por dato):
 *
 *   - PROBADO (`artist/title/album/year/label`, `source` ≠ 'none'): link a
 *     catálogo, bloque Topic, campos "Album:" a mano. El pipeline los toma como
 *     identificación.
 *   - PARSEADO (`titleHints`, `artistFromChannel`): convenciones de título de
 *     canales digger ("[US] Soul, Jazz (1980)") y el nombre del canal cuando el
 *     canal ES el artista. Van con `method: 'parsed'` y confidence, NUNCA se
 *     escriben en campos de catálogo: el pipeline decide con provenance.
 */
import type { Credit } from './entities'
import { canalDe } from './canales'
import { INVISIBLES, cleanTitle, similarity, splitArtistTitle } from './fuzzy'
import { GENRE_WORDS } from './taxonomy'

/** De dónde salió la pista. Ordenado de más a menos confiable. */
export type HintSource = 'catalog_link' | 'topic_channel' | 'labeled_fields' | 'none'

/** Convenciones de título de canales digger que sabemos leer (brief §4). */
export type TitleConvention =
  /** Music for empty rooms: "Artista - Título [País] Género, Género (Año)" */
  | 'pais-genero-anio'
  /** ants kask: "Artista - Título - 1982 - Japan" */
  | 'anio-pais'
  /** Crackle Journey: "Artista - Título [Género] (1980 - País)" */
  | 'genero-anio-pais'
  /** Music for empty rooms, Antonio Pérez: "(Library, 1980)" */
  | 'library'
  /** My Vinyl Collection: "Artista - Álbum (1983) - A3 - Título" */
  | 'album-posicion'
  /** foreal: "Artista - Título (Jazz Funk) (City Pop) (Japan) (1979)" */
  | 'parentesis'
  /** "八神純子 - 夜空のイヤリング (1983) Junko Yagami - Night Sky Earrings" */
  | 'bilingue'
  /** Sample Soul 70, si: "Artista – Título (1975)" */
  | 'anio'

/**
 * Lo que dice el TÍTULO según la convención del canal. Es la taxonomía del
 * uploader, no la de Discogs: `genres` son sus palabras, `year` es lo que él
 * escribió. Sirve para buscar mejor (país y año acotan Discogs) y para mostrar
 * "del título" en la ficha, no para afirmar catálogo.
 */
export interface TitleHints {
  convention: TitleConvention
  artist?: string
  title?: string
  album?: string
  /** posición en el disco ("A3") cuando el uploader la pone */
  position?: string
  year?: number
  /** país normalizado a como lo escribe Discogs ("US", "UK", "Japan", "Brazil") */
  country?: string
  genres?: string[]
  /** el mismo artista en otro alfabeto (romaji / kanji), para reintentar catálogo */
  artistAlias?: string
  titleAlias?: string
  method: 'parsed'
  confidence: number
}

/** El nombre del canal cuando el canal ES el artista ("The Blackbyrds | Mysterious Vibes"). */
export interface ChannelArtistHint {
  value: string
  /** el mismo nombre en otro alfabeto, si el canal lo escribe bilingüe */
  alias?: string
  method: 'parsed'
  confidence: number
  /** 'official': el nombre dice Official/公式; 'name': parece un nombre y nada más */
  reason: 'official' | 'name'
}

export interface YtHints {
  artist?: string
  title?: string
  album?: string
  /** año de la OBRA según la evidencia; undefined si solo sabemos el de una reedición */
  year?: number
  /** 0..1 — cuánto creemos que `year` es el año de la obra y no de la edición */
  yearConfidence?: number
  /** el ℗ tal cual: puede ser de una reedición digital (℗ 2013 para un LP de 1973) */
  phonogramYear?: number
  /** año de "Released on:" del bloque Topic */
  releasedOn?: number
  /** true cuando el bloque huele a reedición/recopilatorio: no usar el ℗ como año de la obra */
  reissue?: boolean
  label?: string
  discogsReleaseId?: number
  discogsMasterId?: number
  recordingMbid?: string
  releaseMbid?: string
  /**
   * Nombres alternativos sacados de los tags y de los artistas secundarios del
   * bloque Topic: el mismo artista en romaji, kanji y katakana. No afirmamos
   * cuál es el artista, pero sirven para reintentar el match con el nombre que
   * use cada catálogo.
   */
  aliases: string[]
  /** créditos por rol de la descripción Topic ("Piano: X"); instrumentos gratis */
  credits: Credit[]
  /** convención de título del canal, parseada. Ver `TitleHints`. */
  titleHints?: TitleHints
  /** el canal como artista, cuando el título no trae "Artista - Tema". Ver `ChannelArtistHint`. */
  artistFromChannel?: ChannelArtistHint
  source: HintSource
  /** 0..1 — qué tan fuerte es la evidencia, no qué tan completa */
  confidence: number
}

export const NO_HINTS: YtHints = { aliases: [], credits: [], source: 'none', confidence: 0 }

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
 *   Released on: <aaaa-mm-dd>
 *   [<Rol>: <nombre> …]
 *   Auto-generated by YouTube.
 *
 * Cuando la descripción llega con los saltos de línea colapsados (fixtures,
 * scrapers), se recorta usando el título del video y el nombre del canal como
 * marcas: el título del video de un Topic ES el título del tema, y el canal
 * ES el artista.
 */
const TOPIC_CHANNEL = /\s-\sTopic$/
const PROVIDED_BY = /Provided to YouTube by\s+/i
const PHONOGRAM = /℗\s*(?:originally released\s*(?:in\s*)?)?(\d{4})?\.?\s*/i
const RELEASED_ON = /Released on:\s*(\d{4})(?:-\d{2}(?:-\d{2})?)?/i
/** dónde termina un campo del bloque Topic cuando está todo en una línea */
const FIN_DE_CAMPO = /\s+(?:Released on:|Auto-generated by|©|™|WARNING:|All rights reserved|[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+){0,2}:\s)/
/** el disco es una reedición / recopilatorio: el ℗ no es el año de la obra */
const REEDICION =
  /\b(remaster(ed)?|complete|anthology|greatest hits|best of|the best|collection|recordings|deluxe|expanded|box set|previously unreleased|essential|rarities|reissue|compilation|hits|singles|retrospective|20th|25th|30th|40th|50th|anniversary)\b/i
/** sellos que SOLO reeditan: su ℗ es siempre el de la reedición */
const SELLOS_DE_REEDICION =
  /(athens of the north|dust index|numero group|light in the attic|kudos ?records|jazzman|soul jazz records|wewantsounds|be with records|mr\.? bongo|strut records|ace records|kent records|expansion records|cherry red|big break records|funky ?town grooves|demon music|vinyl me,? please|now-again|luv n' haight|ubiquity|jazz room|favorite recordings|tidal waves music|outernational|cultures of soul|super disco edits|izipho|mad about records|dynamite cuts|terrestrial funk|rain&shine|rain & shine)/i

// ---------- roles → instrumentos (para `credits`) ----------

/** rol de la descripción Topic → instrumento de `taxonomy.KEY_INSTRUMENTS` */
const ROL_A_INSTRUMENTO: ReadonlyArray<[RegExp, string]> = [
  [/\b(electric piano|fender rhodes|rhodes)\b/i, 'Rhodes'],
  [/\bwurlitzer\b/i, 'Wurlitzer'],
  [/\bharpsichord\b/i, 'harpsichord'],
  [/\bpiano\b/i, 'piano'],
  [/\b(organ|hammond)\b/i, 'organ'],
  [/\bclavinet\b/i, 'clavinet'],
  [/\b(synth(esizer)?s?|moog|arp)\b/i, 'synth'],
  [/\bguitar\b/i, 'guitar'],
  [/\bbass\b/i, 'bass'],
  [/\bdrums?\b/i, 'drums'],
  [/\b(percussion|congas?|bongos?|timbales)\b/i, 'percussion'],
  [/\bflute\b/i, 'flute'],
  [/\b(sax(ophone)?)\b/i, 'saxophone'],
  [/\b(trumpet|flugelhorn)\b/i, 'trumpet'],
  [/\btrombone\b/i, 'trombone'],
  [/\bharp\b/i, 'harp'],
  [/\b(vibraphone|vibes)\b/i, 'vibraphone'],
  [/\b(strings|violin|viola|cello)\b/i, 'strings'],
  [/\b(vocals?|voice)\b/i, 'vocals'],
  [/\b(choir|chorus)\b/i, 'choir'],
]

/** roles que aparecen en el bloque Topic (para reconocerlos en texto plano) */
const ROLES_CONOCIDOS =
  '(?:Composer|Lyricist|Producer|Co-Producer|Arranger|Writer|Main Artist|Featured Artist|Associated Performer|Performance|Studio Personnel|Recording Engineer|Mixing Engineer|Mastering Engineer|Remixing Engineer|Engineer|Mixer|Conductor|Vocal Arranger|Music Publisher|Piano|Electric Piano|Fender Rhodes|Rhodes|Wurlitzer|Keyboards|Synthesizer|Organ|Clavinet|Guitar|Electric Guitar|Acoustic Guitar|Bass|Electric Bass|Bass Guitar|Drums|Percussion|Congas|Flute|Saxophone|Alto Saxophone|Tenor Saxophone|Soprano Saxophone|Baritone Saxophone|Trumpet|Flugelhorn|Trombone|Harp|Vibraphone|Vibes|Strings|Violin|Viola|Cello|Vocals|Vocal|Lead Vocals|Background Vocals|Backing Vocals|Choir|Harpsichord)'
const ROL_LINEA = /^([A-Za-z][A-Za-z ,/&-]{1,40}):\s*(.+)$/
const ROL_PLANO = new RegExp(
  `(?:^|\\s)(${ROLES_CONOCIDOS}(?:,\\s*${ROLES_CONOCIDOS})*):\\s*(.+?)(?=\\s+${ROLES_CONOCIDOS}(?:,\\s*${ROLES_CONOCIDOS})*:\\s|\\s+Auto-generated|\\s+Released on:|$)`,
  'g',
)
/** la línea que sigue a "tema · artista" es el disco, salvo que ya sea el ℗ o un rol ("Love: Part 2" sí es un disco) */
const NO_ES_ALBUM = new RegExp(String.raw`^(?:℗|Released on:|Auto-generated|${ROLES_CONOCIDOS}(?:,\s*${ROLES_CONOCIDOS})*:\s)`)
/** claves que parecen rol pero no lo son */
const NO_ES_ROL = /^(released on|warning|album|álbum|year|año|label|sello|artist|artista|lp|disco|from the album|note|notes)$/i

function instrumentoDe(rol: string): string | undefined {
  for (const [re, inst] of ROL_A_INSTRUMENTO) if (re.test(rol)) return inst
  return undefined
}

function creditosDe(rolesCrudos: Array<[string, string]>): Credit[] {
  const out: Credit[] = []
  const vistos = new Set<string>()
  for (const [claves, valor] of rolesCrudos) {
    const name = clean(valor.replace(/\s+Auto-generated.*$/i, ''))
    if (!name || name.length > 60) continue
    for (const rol of claves.split(/\s*,\s*/)) {
      const role = rol.trim()
      if (!role || NO_ES_ROL.test(role)) continue
      const k = `${role}|${name}`.toLowerCase()
      if (vistos.has(k)) continue
      vistos.add(k)
      out.push({ name, role, instrument: instrumentoDe(role) })
    }
  }
  return out
}

/** Roles línea a línea (forma real) o por vocabulario conocido (forma plana). */
function parseRoles(description: string, plano: boolean): Credit[] {
  if (plano) {
    const pares: Array<[string, string]> = []
    for (const m of description.matchAll(ROL_PLANO)) pares.push([m[1], m[2]])
    return creditosDe(pares)
  }
  const pares: Array<[string, string]> = []
  for (const linea of description.split(/\r?\n/)) {
    const m = linea.trim().match(ROL_LINEA)
    if (m) pares.push([m[1], m[2]])
  }
  return creditosDe(pares)
}

// ---------- campos etiquetados a mano ----------

/**
 * "Album: X", "Album : X", indentado. Ojo: en un template literal `\s` se
 * convierte en "s" — este bug dejaba el regex como `^s*albums*:s*` y solo
 * funcionaba de casualidad con "Album: X" pegado al margen.
 */
const FIELD = (names: string): RegExp => new RegExp(String.raw`^\s*(?:${names})\s*:\s*(.+)$`, 'im')
const FROM_ALBUM = /from the album\s*["“”']([^"“”']+)["“”'],?\s*(\d{4})?/i
/** canal "true to beats": "LP : <disco> <sello> <año> <país>" */
const LP_LINE = /^\s*LP\s*:\s*(.+?)(?:\s+(19[2-9]\d|20[0-2]\d))?(?:\s+(USA|UK|Japan|Brazil|France|Italy|Germany|Canada))?\s*$/im
/** en texto plano el valor de un campo termina donde empieza el siguiente */
const SIGUIENTE_CAMPO = /\s+[A-Za-zÀ-ÿ]{2,12}\s*:\s/

const clean = (s: string | undefined): string | undefined => {
  const t = s?.trim().replace(/\s{2,}/g, ' ')
  return t || undefined
}

function toYear(raw: string | undefined): number | undefined {
  const m = raw?.match(/\b(19[2-9]\d|20[0-2]\d)\b/)
  return m ? Number(m[1]) : undefined
}

const sinAcentos = (s: string): string =>
  s
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .trim()

/** "Sharon Ridley Stay a While with Me" empieza con "Sharon Ridley" → el resto es el disco. */
function sacarPrefijo(texto: string, prefijo: string): string | undefined {
  const t = sinAcentos(texto)
  const p = sinAcentos(prefijo)
  if (!p || !t.startsWith(p)) return undefined
  return texto.slice(prefijo.length).trim()
}

interface TopicParse extends Partial<YtHints> {
  aliasesTopic: string[]
}

/** Parsea el bloque de un canal "- Topic". Devuelve null si no tiene esa forma. */
function parseTopic(channelTitle: string, description: string, videoTitle?: string): TopicParse | null {
  if (!TOPIC_CHANNEL.test(channelTitle) && !PROVIDED_BY.test(description)) return null
  if (!description.includes(' · ')) return null

  const canalArtista = clean(channelTitle.replace(TOPIC_CHANNEL, ''))
  const plano = !/\n/.test(description)

  let rawTitle: string | undefined
  let artists: string[] = []
  let album: string | undefined

  if (!plano) {
    const lines = description
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter(Boolean)
    // la línea "tema · artista" es la primera con separador de punto medio
    const i = lines.findIndex((l) => l.includes(' · '))
    if (i === -1) return null
    ;[rawTitle, ...artists] = lines[i].split(' · ').map((p) => p.trim())
    // la línea siguiente al bloque de artistas es el disco (si no es ya el ℗)
    const next = lines[i + 1]
    if (next && !NO_ES_ALBUM.test(next)) album = next
  } else {
    // forma plana: "Provided to YouTube by X <tema> · <artista> <disco> ℗ ..."
    // La distribuidora y el tema quedan pegados sin marca; el título del video
    // de un Topic ES el título del tema, así que se usa ese y listo.
    let cuerpo = description.replace(/^[\s\S]*?Provided to YouTube by\s+/i, '')
    cuerpo = cuerpo.split(/\s*℗|\s+Released on:|\s+Auto-generated/)[0] ?? cuerpo
    const partes = cuerpo.split(' · ').map((p) => p.trim())
    if (partes.length < 2) return null
    rawTitle = videoTitle
    const medio = partes.slice(1, -1)
    const cola = partes[partes.length - 1]
    // la cola es "<artistaN> <disco>": si empieza con el nombre del canal, lo que sobra es el disco
    const resto = canalArtista ? sacarPrefijo(cola, canalArtista) : undefined
    if (resto !== undefined) {
      artists = [...medio, canalArtista as string]
      album = resto || undefined
    } else {
      // sin marca no hay cómo partir "<artista> <disco>": se pierde el disco, el
      // artista sale del canal (abajo) y los del medio quedan como aliases
      artists = medio
      album = undefined
    }
  }

  // el canal ES el artista (YouTube crea el Topic por entidad de artista): si
  // está entre los créditos, manda; el resto son intérpretes y van a aliases
  let artist: string | undefined
  const idx = canalArtista
    ? artists.findIndex((a) => similarity(a, canalArtista) >= 0.85 || sinAcentos(a) === sinAcentos(canalArtista))
    : -1
  if (idx >= 0) artist = artists[idx]
  // en la forma plana el artista principal se perdió pegado al disco: manda el canal
  else artist = plano ? (canalArtista ?? clean(artists[0])) : (clean(artists[0]) ?? canalArtista)
  const aliasesTopic = [...artists, canalArtista ?? '']
    .map((a) => clean(a))
    .filter((a): a is string => Boolean(a) && sinAcentos(a as string) !== sinAcentos(artist ?? ''))

  // ---- año: ℗ vs Released on vs reedición ----
  const phono = description.match(PHONOGRAM)
  const phonogramYear = phono ? toYear(phono[1]) : undefined
  let label: string | undefined
  if (phono && phono.index != null) {
    const despues = description.slice(phono.index + phono[0].length)
    const corte = despues.search(FIN_DE_CAMPO)
    const lineaFin = despues.search(/\r?\n/)
    const fin = [corte, lineaFin].filter((x) => x >= 0)
    label = clean(despues.slice(0, fin.length ? Math.min(...fin) : undefined).replace(/^©\s*/, ''))
    if (label && label.length > 60) label = undefined
  }
  const releasedOn = toYear(description.match(RELEASED_ON)?.[1])
  // "℗ 1983, 2025 WARNER": el segundo año es el de la remasterización
  const segundoAnio = phono ? toYear(description.slice(phono.index ?? 0).match(/℗[^\n]{0,20}?\d{4}\s*[,/]\s*(\d{4})/)?.[1]) : undefined
  // el año del título del disco cuenta ("Live 1975"), un rango no ("Detroit: 1969 - 1977")
  const anioDelAlbum = album && !/\d{4}\s*[-–—]\s*\d{4}/.test(album) ? toYear(album) : undefined

  /**
   * El ℗ es el año de la GRABACIÓN… cuando la distribuidora lo respeta. Las
   * reediciones digitales ponen el suyo (℗ 2013 Dust Index para un LP de 1973;
   * medido: 13 de 78 Topic del benchmark). Se cruza con "Released on:", con el
   * título del disco y con el sello:
   *
   *   - sin señal de reedición → el ℗ es el año (0.85); si solo hay Released
   *     on, ese (0.6).
   *   - con señal de reedición → el año de la EDICIÓN es el más nuevo de los
   *     que tenemos, y la obra es el más viejo, siempre que sea anterior al
   *     2000 (un ℗ 2001 en "20 Greatest Hits" es el del recopilatorio, no el
   *     del tema). Si no queda nada, `year` va vacío y el catálogo decide.
   */
  const candidatos = [phonogramYear, releasedOn, anioDelAlbum, segundoAnio].filter((y): y is number => y != null)
  const edicion = candidatos.length ? Math.max(...candidatos) : undefined
  const masViejo = candidatos.length ? Math.min(...candidatos) : undefined
  // señal FUERTE: el disco se llama recopilatorio, el sello solo reedita, o el ℗ trae dos años
  const senalFuerte = Boolean((album && REEDICION.test(album)) || (label && SELLOS_DE_REEDICION.test(label)) || segundoAnio != null)
  // señal DÉBIL: entre el ℗ y el Released on hay 2+ años (1 año es distribución normal)
  const brecha = edicion != null && masViejo != null && edicion - masViejo >= 2
  const reissue = senalFuerte || brecha

  let year: number | undefined
  let yearConfidence: number | undefined
  if (!reissue) {
    if (phonogramYear != null) {
      year = phonogramYear
      yearConfidence = releasedOn == null || releasedOn === phonogramYear ? 0.85 : 0.75
    } else if (releasedOn != null) {
      year = releasedOn
      yearConfidence = 0.6
    }
  } else if (senalFuerte) {
    // con recopilatorio/sello de reedición, un ℗ del 2000 en adelante es el de la edición
    const viejos = candidatos.filter((y) => edicion != null && y < edicion && (y < 2000 || y === anioDelAlbum))
    if (viejos.length) {
      year = Math.min(...viejos)
      yearConfidence = 0.7
    } else if (phonogramYear != null && phonogramYear < 2000 && releasedOn == null) {
      // "Best Collection ℗ 1983": el sello japonés conservó el ℗ original
      year = phonogramYear
      yearConfidence = 0.6
    }
  } else {
    // solo brecha: la distribuidora conservó el ℗ viejo (Klemmer ℗ 1976 / Released on 1996)
    // o puso el de la reedición (Majestic Arrows ℗ 2013 / Released on 1973). El más viejo manda.
    year = masViejo
    yearConfidence = masViejo != null && masViejo < 2000 ? 0.7 : 0.5
  }

  return {
    title: clean(rawTitle),
    artist,
    album: clean(album),
    year,
    yearConfidence,
    phonogramYear,
    releasedOn,
    reissue: reissue || undefined,
    label,
    credits: parseRoles(description, plano),
    aliasesTopic,
  }
}

/** Campos escritos a mano por el uploader: "Album: X", "Year: 1986", "LP : …". */
function parseFields(description: string): Partial<YtHints> {
  const grab = (names: string): string | undefined => {
    const v = description.match(FIELD(names))?.[1]
    if (!v) return undefined
    // en texto plano el valor sigue hasta el próximo "Campo:"
    const corte = v.search(SIGUIENTE_CAMPO)
    return clean(corte >= 0 ? v.slice(0, corte) : v)
  }
  const fromAlbum = description.match(FROM_ALBUM)
  const lp = description.match(LP_LINE)
  return {
    album: grab('album|álbum|disco|アルバム') ?? clean(fromAlbum?.[1]) ?? clean(lp?.[1]),
    year:
      toYear(grab('year|año|anno|ano|jahr|année|年')) ??
      toYear(fromAlbum?.[2]) ??
      toYear(lp?.[2]),
    label: grab('label|sello|gravadora|レーベル'),
    artist: grab('artist|artista|アーティスト'),
  }
}

// ---------- convenciones de título de canales digger ----------

/** país como lo escribe el uploader → como lo escribe Discogs */
const PAISES: Record<string, string> = {
  us: 'US', usa: 'US', 'u.s.a.': 'US', 'u.s.a': 'US', 'united states': 'US', america: 'US',
  uk: 'UK', 'u.k.': 'UK', england: 'UK', 'united kingdom': 'UK', 'great britain': 'UK', britain: 'UK', scotland: 'UK', wales: 'UK',
  japan: 'Japan', jp: 'Japan', japon: 'Japan', japón: 'Japan', 日本: 'Japan',
  brazil: 'Brazil', brasil: 'Brazil',
  france: 'France', italy: 'Italy', italia: 'Italy', germany: 'Germany', 'west germany': 'Germany', deutschland: 'Germany',
  canada: 'Canada', netherlands: 'Netherlands', holland: 'Netherlands', belgium: 'Belgium', spain: 'Spain', españa: 'Spain',
  sweden: 'Sweden', norway: 'Norway', denmark: 'Denmark', finland: 'Finland', switzerland: 'Switzerland', austria: 'Austria',
  poland: 'Poland', hungary: 'Hungary', czechoslovakia: 'Czechoslovakia', yugoslavia: 'Yugoslavia', sfry: 'Yugoslavia',
  serbia: 'Yugoslavia', croatia: 'Yugoslavia', slovenia: 'Yugoslavia', ussr: 'USSR',
  'soviet union': 'USSR', bulgaria: 'Bulgaria', romania: 'Romania', greece: 'Greece', turkey: 'Turkey', portugal: 'Portugal',
  ireland: 'Ireland', israel: 'Israel', lebanon: 'Lebanon', iran: 'Iran', egypt: 'Egypt',
  argentina: 'Argentina', mexico: 'Mexico', méxico: 'Mexico', peru: 'Peru', perú: 'Peru', chile: 'Chile', colombia: 'Colombia',
  venezuela: 'Venezuela', cuba: 'Cuba', haiti: 'Haiti', jamaica: 'Jamaica', 'puerto rico': 'Puerto Rico', uruguay: 'Uruguay',
  nigeria: 'Nigeria', ghana: 'Ghana', 'south africa': 'South Africa', ethiopia: 'Ethiopia', senegal: 'Senegal', kenya: 'Kenya',
  australia: 'Australia', 'new zealand': 'New Zealand', korea: 'South Korea', 'south korea': 'South Korea',
  philippines: 'Philippines', indonesia: 'Indonesia', thailand: 'Thailand', india: 'India', 'hong kong': 'Hong Kong',
  taiwan: 'Taiwan', singapore: 'Singapore', malaysia: 'Malaysia',
}

/** "US", "Bulgaria/USSR" → "US", "Bulgaria". undefined si no es un país. */
function paisDe(raw: string | undefined): string | undefined {
  if (!raw) return undefined
  const primero = raw.split(/\s*[/,&]\s*/)[0]
  return PAISES[sinAcentos(primero)] ?? PAISES[primero.trim().toLowerCase()]
}

const ANIO = String.raw`(19[2-9]\d|20[0-2]\d)`
const SEPARADOR = String.raw`\s+[-–—~]{1,2}\s+`
const CJK = String.raw`[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}]`
/** letras latinas con acentos (Ōnuki, Kostić): el bloque Latin-1 + Latin Extended */
const LATIN = String.raw`[A-Za-z\u00C0-\u024F]`

const RE_ALBUM_POSICION = new RegExp(String.raw`^(.+?)${SEPARADOR}(.+?)\s*\(${ANIO}\)${SEPARADOR}([A-D]\d{1,2})${SEPARADOR}(.+)$`, 'u')
const RE_PAIS_GENERO_ANIO = new RegExp(String.raw`^(.+?)${SEPARADOR}(.+?)\s*\[([^\]]{2,40})\]\s*([^()\[\]]*?)\s*\(${ANIO}\)\s*$`, 'u')
const RE_GENERO_ANIO_PAIS = new RegExp(String.raw`^(.+?)${SEPARADOR}(.+?)\s*\[([^\]]{2,40})\]\s*\(${ANIO}\s*[-–—]\s*([A-Za-z .]+)\)\s*$`, 'u')
const RE_ANIO_PAIS = new RegExp(String.raw`^(.+?)${SEPARADOR}(.+?)${SEPARADOR}${ANIO}${SEPARADOR}([A-Za-z .]+)\s*$`, 'u')
const RE_LIBRARY = new RegExp(String.raw`^(?:(.+?)${SEPARADOR})?(.+?)\s*\(Library,?\s*${ANIO}\)`, 'iu')
const RE_PARENTESIS = new RegExp(String.raw`^(?:(.+?)${SEPARADOR})?(.+?)((?:\s*\([^()]{2,25}\)){2,})\s*$`, 'u')
const RE_BILINGUE = new RegExp(
  String.raw`^(${CJK}[^-–—]*?)${SEPARADOR}([^(]+?)\s*\(${ANIO}\)\s+([A-Za-z][A-Za-z .'&-]+?)${SEPARADOR}(.+)$`,
  'u',
)
const RE_ANIO_SOLO = new RegExp(String.raw`^(.+?)${SEPARADOR}(.+?)\s*[(\[]${ANIO}[)\]]\s*$`, 'u')
const RE_POSICION = /^([A-D]\d{1,2})\s+(.+)$/
const RE_NOMBRE_BILINGUE = new RegExp(String.raw`^(${CJK}[^A-Za-z(]*?)\s*[(/]?\s*(${LATIN}(?:${LATIN}| |[.'&-]){2,})\)?\s*$`, 'u')
const RE_NOMBRE_BILINGUE_INV = new RegExp(String.raw`^(${LATIN}(?:${LATIN}| |[.'&-]){2,}?)\s*\(\s*(${CJK}[^)]*)\)\s*$`, 'u')

const generosDe = (s: string | undefined): string[] | undefined => {
  const g = (s ?? '')
    .split(/\s*[,/]\s*/)
    .map((x) => x.trim())
    .filter((x) => x.length >= 2 && x.length <= 30 && !/\d{4}/.test(x))
  return g.length ? g.slice(0, 6) : undefined
}

/** "西田佐知子 Sachiko Nishida" → { name: '西田佐知子', alias: 'Sachiko Nishida' } */
function nombreBilingue(s: string | undefined): { name?: string; alias?: string } {
  if (!s) return {}
  const m = s.match(RE_NOMBRE_BILINGUE) ?? s.match(RE_NOMBRE_BILINGUE_INV)
  if (!m) return { name: clean(s) }
  return { name: clean(m[1]), alias: clean(m[2]) }
}

/**
 * Lee las convenciones de título de los canales digger. Ordenado de más a
 * menos específico; el primero que pega, gana. Todo lo que devuelve es
 * `parsed`: son las palabras del uploader.
 */
export function parseTitleConventions(raw: string): TitleHints | undefined {
  const t = raw.replace(INVISIBLES, '').trim()
  if (!t) return undefined
  const crudo = parseConvencion(t)
  if (!crudo) return undefined
  // "[Mexico]" colgado del artista es el país; después, artista y título se
  // limpian con el mismo limpiador que usa el pipeline (sin corchetes, sin "HQ")
  const paisEnArtista = crudo.artist?.match(/\[([^\]]{2,30})\]/)
  const country = crudo.country ?? paisDe(paisEnArtista?.[1])
  const artist = crudo.artist ? cleanTitle(crudo.artist) || undefined : undefined
  const title = crudo.title ? cleanTitle(crudo.title) || crudo.title : undefined
  return { ...crudo, artist, title, country }
}

function parseConvencion(t: string): TitleHints | undefined {

  let m = t.match(RE_ALBUM_POSICION)
  if (m) {
    const { name, alias } = nombreBilingue(m[1])
    return {
      convention: 'album-posicion',
      artist: name,
      artistAlias: alias,
      album: clean(m[2]),
      year: Number(m[3]),
      position: m[4],
      title: clean(m[5]),
      method: 'parsed',
      confidence: 0.7,
    }
  }

  m = t.match(RE_BILINGUE)
  if (m) {
    return {
      convention: 'bilingue',
      artist: clean(m[1]),
      title: clean(m[2]),
      year: Number(m[3]),
      artistAlias: clean(m[4]),
      titleAlias: clean(m[5]),
      method: 'parsed',
      confidence: 0.65,
    }
  }

  m = t.match(RE_GENERO_ANIO_PAIS)
  if (m) {
    const country = paisDe(m[5])
    if (country) {
      const { name, alias } = nombreBilingue(m[1])
      return {
        convention: 'genero-anio-pais',
        artist: name,
        artistAlias: alias,
        title: clean(m[2]),
        genres: generosDe(m[3]),
        year: Number(m[4]),
        country,
        method: 'parsed',
        confidence: 0.7,
      }
    }
  }

  m = t.match(RE_PAIS_GENERO_ANIO)
  if (m) {
    const country = paisDe(m[3])
    if (country) {
      const { name, alias } = nombreBilingue(m[1])
      return {
        convention: 'pais-genero-anio',
        artist: name,
        artistAlias: alias,
        title: clean(m[2]),
        country,
        genres: generosDe(m[4]),
        year: Number(m[5]),
        method: 'parsed',
        confidence: 0.7,
      }
    }
  }

  m = t.match(RE_ANIO_PAIS)
  if (m) {
    const country = paisDe(m[4])
    if (country) {
      const { name, alias } = nombreBilingue(m[1])
      const pos = m[2].match(RE_POSICION)
      return {
        convention: 'anio-pais',
        artist: name,
        artistAlias: alias,
        title: clean(pos ? pos[2] : m[2]),
        position: pos?.[1],
        year: Number(m[3]),
        country,
        method: 'parsed',
        confidence: 0.7,
      }
    }
  }

  m = t.match(RE_LIBRARY)
  if (m) {
    const { name, alias } = nombreBilingue(m[1])
    return {
      convention: 'library',
      artist: name,
      artistAlias: alias,
      title: clean(m[2]),
      genres: ['Library'],
      year: Number(m[3]),
      method: 'parsed',
      confidence: 0.65,
    }
  }

  m = t.match(RE_PARENTESIS)
  if (m) {
    const grupos = [...m[3].matchAll(/\(([^()]+)\)/g)].map((g) => g[1].trim())
    let year: number | undefined
    let country: string | undefined
    const genres: string[] = []
    for (const g of grupos) {
      const y = /^(19[2-9]\d|20[0-2]\d)$/.test(g) ? Number(g) : undefined
      const c = paisDe(g)
      if (y) year = y
      else if (c) country = c
      // un grupo es género solo si trae vocabulario de género: "(Take Your Time)" es un subtítulo
      else if (/^[A-Za-z][A-Za-z &-]{1,24}$/.test(g) && g.split(/[\s&-]+/).some((w) => GENRE_WORDS.has(w.toLowerCase()))) genres.push(g)
    }
    if (year && (country || genres.length)) {
      const { name, alias } = nombreBilingue(m[1])
      return {
        convention: 'parentesis',
        artist: name,
        artistAlias: alias,
        title: clean(m[2]),
        year,
        country,
        genres: genres.length ? genres : undefined,
        method: 'parsed',
        confidence: 0.6,
      }
    }
  }

  m = t.match(RE_ANIO_SOLO)
  if (m) {
    const { name, alias } = nombreBilingue(m[1])
    return {
      convention: 'anio',
      artist: name,
      artistAlias: alias,
      title: clean(m[2]),
      year: Number(m[3]),
      method: 'parsed',
      confidence: 0.6,
    }
  }

  return undefined
}

// ---------- el canal como artista ----------

/** sufijos de canal oficial, en los idiomas que aparecen en el crate */
const SUFIJO_OFICIAL =
  /\s*[-–|/]?\s*(?:official\s*(?:artist\s*|music\s*)?(?:youtube\s*)?(?:channel|page)?|oficial|music\s+official|\S*公式.*|オフィシャル.*|official|vevo|youtube\s*channel|チャンネル.*)\s*$/i
const OFICIAL = /(official|oficial|公式|オフィシャル|vevo)/i
/** un canal que se llama así es un digger, un sello o una radio, no el artista */
const VOCABULARIO_DIGGER =
  /(soul|funk|jazz|groove|sample|vinyl|record|music|dig|rare|\btv\b|radio|collection|archive|beats|sounds?\b|club|show|station|channel|production|entertainment|\bent\b|srl|ltd|inc\b|fans?\b|lover|mix|dj\b|beat\b|tunes|audio|library|selection|nuggets|gems|crate|wax|45s|oldies|classics|hits|playlist|lounge|cafe|bar\b|grooves|vibes|sessions|world|planet|zone|station|scene|delicacy|frontier)/i

/**
 * ¿El canal es el artista? Solo cuando el título no trae "Artista - Tema"
 * (si lo trae, el uploader es un digger y el artista ya está en el título).
 * Un nombre oficial (Official / 公式) es evidencia fuerte; un nombre pelado sin
 * vocabulario de digger, débil. Nunca pasa de 0.6: MusicBrainz exige que el
 * artista coincida, así que un uploader equivocado no identifica (falla suave)
 * en vez de identificar mal.
 */
function artistaDeCanal(channelTitle: string | undefined, videoTitle: string | undefined): ChannelArtistHint | undefined {
  if (!channelTitle || !videoTitle) return undefined
  if (TOPIC_CHANNEL.test(channelTitle)) return undefined
  if (splitArtistTitle(videoTitle).artist) return undefined
  if (canalDe(undefined, channelTitle)) return undefined

  // "MAX MEAZZA     AOR / ROCK  /BLUES /JAZZ": lo que sigue a 2+ espacios es la bio, no el nombre
  let nombre = channelTitle.replace(INVISIBLES, '').trim().split(/\s{2,}/)[0]
  const oficial = OFICIAL.test(nombre)
  // "The Voice of Anton :", "Sean Mac (Jpmusic69)", "FOND/SOUND": nombres de canal, no de artista
  if (!oficial && (/[:|#@]/.test(nombre) || /\(/.test(nombre))) return undefined
  // "【由紀さおり公式チャンネル】由紀チャンネル" → lo que está antes de 公式
  const corchetes = nombre.match(/【(.+?)(?:公式|オフィシャル)/)
  if (corchetes) nombre = corchetes[1]
  let previo = ''
  while (previo !== nombre) {
    previo = nombre
    nombre = nombre.replace(SUFIJO_OFICIAL, '').trim()
  }
  nombre = nombre.replace(/[-–|/:]+$/, '').trim()
  if (!nombre) return undefined

  if (!oficial) {
    if (VOCABULARIO_DIGGER.test(nombre)) return undefined
    // handles: "Sheeks15", "otomo2000", "Creme2laCreme"
    if (/\d{2,}/.test(nombre) || /\d$/.test(nombre) || /[A-Za-z]\d[A-Za-z]/.test(nombre)) return undefined
    if (/^[a-z0-9 ._'-]+$/.test(nombre)) return undefined // todo minúsculas: es un handle, no un nombre
    // CamelCase de una sola palabra es un handle ("SeaboardRailroad", "TheDCTDCT");
    // "McDuff", "DeBarge" o "CeCe Winans" no, por eso se exigen 3+ minúsculas antes
    if (!/\s/.test(nombre) && (/[a-z]{3,}[A-Z]/.test(nombre) || /[a-z][A-Z]{2,}/.test(nombre))) return undefined
  }

  const { name, alias } = nombreBilingue(nombre)
  const value = name ?? nombre
  const tokens = value.split(/\s+/).length
  const confidence = oficial ? 0.6 : tokens >= 2 ? 0.45 : 0.35
  return { value, alias, method: 'parsed', confidence, reason: oficial ? 'official' : 'name' }
}

/**
 * Extrae todo lo que se pueda probar del snippet de YouTube.
 * No inventa: si no hay evidencia, devuelve `NO_HINTS` (más lo parseado aparte).
 */
export function extractHints(input: {
  channelTitle?: string
  description?: string
  tags?: string[]
  /** el título del video: para las convenciones de canal y como marca en el bloque Topic */
  title?: string
}): YtHints {
  const desc = input.description ?? ''
  const channel = input.channelTitle ?? ''
  const tagAliases = (input.tags ?? []).map((t) => t.trim()).filter(Boolean)

  const discogsRelease = desc.match(DISCOGS_RELEASE)?.[1]
  const discogsMaster = desc.match(DISCOGS_MASTER)?.[1]
  const mbRecording = desc.match(MB_RECORDING)?.[1]
  const mbRelease = desc.match(MB_RELEASE)?.[1]

  const topic = parseTopic(channel, desc, input.title)
  const fields = parseFields(desc)
  const titleHints = input.title ? parseTitleConventions(input.title) : undefined

  // el link a catálogo es la evidencia más fuerte: es un id, no una interpretación
  const hasLink = Boolean(discogsRelease || discogsMaster || mbRecording || mbRelease)
  const source: HintSource = hasLink
    ? 'catalog_link'
    : topic
      ? 'topic_channel'
      : fields.album || fields.artist
        ? 'labeled_fields'
        : 'none'

  const aliases = Array.from(new Set([...(topic?.aliasesTopic ?? []), ...tagAliases]))

  if (source === 'none') {
    const artistFromChannel = artistaDeCanal(input.channelTitle, input.title)
    return { ...NO_HINTS, aliases, credits: [], titleHints, artistFromChannel }
  }

  const { aliasesTopic: _omit, ...topicHints } = topic ?? { aliasesTopic: [] }
  void _omit
  const merged: Partial<YtHints> = { ...fields, ...stripUndefined(topicHints) }
  const credits = topic?.credits ?? []
  // con link a catálogo la obra está identificada aunque el ℗ sea de reedición;
  // con solo el bloque Topic, la evidencia de OBRA sigue firme pero la de año no
  const confidence =
    source === 'catalog_link' ? 0.95 : source === 'topic_channel' ? (merged.reissue ? 0.85 : 0.9) : 0.7

  return {
    ...merged,
    discogsReleaseId: discogsRelease ? Number(discogsRelease) : undefined,
    discogsMasterId: discogsMaster ? Number(discogsMaster) : undefined,
    recordingMbid: mbRecording?.toLowerCase(),
    releaseMbid: mbRelease?.toLowerCase(),
    aliases,
    credits,
    titleHints,
    artistFromChannel: merged.artist ? undefined : artistaDeCanal(input.channelTitle, input.title),
    source,
    confidence,
  }
}

/** Quita las claves en undefined para que no pisen valores buenos al hacer spread. */
function stripUndefined<T extends object>(o: T): Partial<T> {
  return Object.fromEntries(Object.entries(o).filter(([, v]) => v !== undefined)) as Partial<T>
}
