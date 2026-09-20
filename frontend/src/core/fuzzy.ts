/**
 * Fuzzy matching — de títulos sucios de YouTube a entidades limpias.
 * "T. Yamashita ~ Sparkle (1982) [Vinyl Rip] HQ"  →  "tatsuro yamashita sparkle"
 * Ver docs/ENTITY_MODEL.md
 */

import { GENRE_WORDS } from './taxonomy'

// ruido típico de uploads de digging
const NOISE_PATTERNS: RegExp[] = [
  /\[[^\]]*\]/g, // [Vinyl Rip], [HQ], [Full Album]
  /\([^)]*\)/g, // (1982), (Official Audio), (Remastered)
  /\b(hq|hd|4k|full\s*album|full\s*lp|vinyl\s*rip|vinyl|lp|ep|official|audio|video|music\s*video|lyrics?|remaster(ed)?|reissue|hi[- ]?fi|rare|classic)\b/gi,
  /\.(wmv|mp4|mp3|flac|avi|mov|wav|m4a)\b/gi, // "Let Me Down Easy.wmv": el nombre del archivo subido tal cual
  /[|/~•·★☆♪♫➤▶]+/g, // separadores/decorados
  /\s{2,}/g,
]

/**
 * Caracteres invisibles que Discogs pega al copiar ("Jean Claudric ‎– En Se
 * Prenant"): marcas de dirección, zero-width, BOM. No son espacio para `\s`,
 * así que el separador " – " no se reconocía y el artista se perdía.
 */
export const INVISIBLES = /[\u200b-\u200f\u2028-\u202e\u2060\ufeff]/g

// Separadores de "Artista - Título". Ojo: hay que partir ANTES de limpiar,
// porque NOISE_PATTERNS borra ~ | / como decorado y se lleva el separador puesto.
// El guion puede venir doble ("Akira Ishikawa -- Sunrise").
const SEP = /\s+(?:[-–—~]{1,2}|[|/])\s+/
/**
 * Guion con espacio de UN solo lado: "The Dramatics- In the rain", "Maxi
 * Anderson -By Your Side". Solo guiones y tilde, nunca `/` ni `|` (partirían
 * "AC/DC"). "Jean-Claude" no se parte porque no tiene espacio de ningún lado.
 * Medido sobre el pool del 19-sep: baja los títulos sin artista de 337 a ~300.
 */
const SEP_ASIMETRICO = /\s+[-–—~]{1,2}(?=\S)|(?<=\S)[-–—~]{1,2}\s+/
/**
 * Dos o más espacios como separador: "CARRIE LUCAS   LOVIN IS ON MY MIND"
 * (TheRAREGROOVEMAN, Casen Fike, AUGUSTA GA 60'S). Va último y solo si no hubo
 * guion; puede invertir artista/título cuando el uploader pone el artista al
 * final ("Make Up for Lost Time   Ted Taylor") — se acepta y MusicBrainz decide.
 */
const SEP_ESPACIOS = /\s{2,}/
// misma idea sin espacios alrededor: "横山みゆき/Miyuki Second", "Kei Marimura ／ MUCHO MUCHO"
const TIGHT_SEP = /\s*[/|／｜]\s*/

export function cleanTitle(raw: string): string {
  let s = raw.replace(INVISIBLES, '')
  for (const p of NOISE_PATTERNS) s = s.replace(p, ' ')
  return dropTrailingGenres(s.trim().replace(/\s{2,}/g, ' '))
}

/**
 * Saca la lista de géneros que los canales de digging cuelgan al final:
 * "Distances Jazz, Soul, Balearic Fusion" → "Distances".
 *
 * Exige DOS o más géneros seguidos al final. Con uno solo no se toca, porque
 * hay discos que se llaman "Blue Jazz" y recortarlos sería peor que dejarlos.
 */
function dropTrailingGenres(s: string): string {
  const tokens = s.split(/\s*,\s*|\s+/).filter(Boolean)
  let end = tokens.length
  while (end > 1 && GENRE_WORDS.has(tokens[end - 1].toLowerCase())) end--

  const recortados = tokens.length - end
  if (recortados < 2 || end === 0) return s
  return tokens.slice(0, end).join(' ')
}

/** Extrae el año (19xx/20xx) si aparece en el texto original. */
export function extractYear(raw: string): number | undefined {
  const m = raw.match(/\b(19[2-9]\d|20[0-2]\d)\b/)
  return m ? Number(m[1]) : undefined
}

/**
 * Separa "Artista - Título" heurísticamente. Devuelve el original limpio si no puede.
 *
 * Parte sobre el texto CRUDO y limpia cada mitad después: al revés, el limpiador
 * se come los separadores decorativos y el artista se pierde. Medido sobre las
 * playlists reales, ese orden dejaba a la mitad de los temas sin artista.
 */
export function splitArtistTitle(raw: string): { artist?: string; title?: string } {
  const limpio = raw.replace(INVISIBLES, '')

  const parts = limpio.split(SEP)
  if (parts.length >= 2) {
    const artist = cleanTitle(parts[0])
    const title = cleanTitle(dropTrailingMeta(parts.slice(1)).join(' - '))
    if (artist && title) return { artist, title }
  }

  // guion con espacio de un solo lado: se parte por el PRIMERO nada más
  const asim = limpio.match(SEP_ASIMETRICO)
  if (asim && asim.index != null) {
    const izq = limpio.slice(0, asim.index)
    const der = limpio.slice(asim.index + asim[0].length)
    const artist = cleanTitle(izq)
    const title = cleanTitle(dropTrailingMeta(der.split(SEP)).join(' - '))
    // el título tiene que tener letras: "Live at Montreux -1975" no es artista + tema
    if (artist.length >= 2 && title.length >= 2 && /\p{L}/u.test(title)) return { artist, title }
  }

  const tight = limpio.split(TIGHT_SEP)
  if (tight.length === 2) {
    const artist = cleanTitle(tight[0])
    const title = cleanTitle(tight[1])
    // el mínimo evita partir cosas como "AC/DC" cuando no hay separador real
    if (artist.length >= 3 && title.length >= 3) return { artist, title }
  }

  // dos o más espacios: 2 o 3 segmentos, no más (4+ es un título con basura)
  const espacios = limpio
    .split(SEP_ESPACIOS)
    .map((s) => s.trim())
    .filter(Boolean)
  if (espacios.length === 2 || espacios.length === 3) {
    const artist = cleanTitle(espacios[0])
    const title = cleanTitle(dropTrailingMeta(espacios.slice(1)).join(' '))
    if (artist.length >= 3 && title.length >= 3 && /\p{L}/u.test(title)) return { artist, title }
  }

  return { title: cleanTitle(limpio) }
}

/**
 * Saca los segmentos finales que son metadata y no parte del título:
 * "Miracle Touch - 1986 - Japan" → "Miracle Touch". Los diggers los cuelgan
 * al final separados igual que el artista, así que el split se los lleva.
 */
const TRAILING_META =
  /^(19[2-9]\d|20[0-2]\d|japan|japon|japón|usa|u\.s\.a\.|uk|brazil|brasil|france|italy|italia|germany|canada|netherlands|holland|belgium|spain|sweden|norway|denmark|finland|switzerland|austria|poland|hungary|yugoslavia|ussr|bulgaria|greece|turkey|portugal|argentina|mexico|méxico|peru|perú|chile|colombia|venezuela|cuba|haiti|jamaica|nigeria|ghana|south africa|australia|korea|indonesia|philippines|india|jp|us|full album|lp|ep|vinyl|audio|official audio|official video|hq|hd|remastered|soul sample|sample|rare soul)$/i

function dropTrailingMeta(parts: string[]): string[] {
  const out = [...parts]
  while (out.length > 1 && TRAILING_META.test(out[out.length - 1].trim())) out.pop()
  return out
}

/** Distancia de Levenshtein (iterativa, O(n·m) memoria O(min)). */
export function levenshtein(a: string, b: string): number {
  if (a === b) return 0
  if (a.length === 0) return b.length
  if (b.length === 0) return a.length
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i)
  let curr = new Array<number>(b.length + 1)
  for (let i = 1; i <= a.length; i++) {
    curr[0] = i
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1
      curr[j] = Math.min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
    }
    ;[prev, curr] = [curr, prev]
  }
  return prev[b.length]
}

const normalize = (s: string): string =>
  s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '') // sacar acentos (combining diacritics)
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s{2,}/g, ' ')
    .trim()

/** Similitud 0..1 (1 = idénticos) sobre strings normalizados. */
export function similarity(a: string, b: string): number {
  const x = normalize(a)
  const y = normalize(b)
  if (!x && !y) return 1
  const maxLen = Math.max(x.length, y.length)
  if (maxLen === 0) return 1
  return 1 - levenshtein(x, y) / maxLen
}

export interface MatchResult<T> {
  item: T
  score: number
}

/**
 * Mejor match de `query` contra candidatos. Devuelve null si nadie supera `threshold`.
 * El `score` devuelto se usa como confidence de la entidad.
 */
export function bestMatch<T>(
  query: string,
  candidates: Array<{ item: T; text: string }>,
  threshold = 0.72,
): MatchResult<T> | null {
  let best: MatchResult<T> | null = null
  for (const c of candidates) {
    const score = similarity(query, c.text)
    if (!best || score > best.score) best = { item: c.item, score }
  }
  return best && best.score >= threshold ? best : null
}
