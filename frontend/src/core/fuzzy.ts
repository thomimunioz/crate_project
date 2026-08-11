/**
 * Fuzzy matching — de títulos sucios de YouTube a entidades limpias.
 * "T. Yamashita ~ Sparkle (1982) [Vinyl Rip] HQ"  →  "tatsuro yamashita sparkle"
 * Ver docs/ENTITY_MODEL.md
 */

// ruido típico de uploads de digging
const NOISE_PATTERNS: RegExp[] = [
  /\[[^\]]*\]/g, // [Vinyl Rip], [HQ], [Full Album]
  /\([^)]*\)/g, // (1982), (Official Audio), (Remastered)
  /\b(hq|hd|4k|full\s*album|full\s*lp|vinyl\s*rip|vinyl|lp|ep|official|audio|video|music\s*video|lyrics?|remaster(ed)?|reissue|hi[- ]?fi|rare|classic)\b/gi,
  /[|/~•·★☆♪♫➤▶]+/g, // separadores/decorados
  /\s{2,}/g,
]

// Separadores de "Artista - Título". Ojo: hay que partir ANTES de limpiar,
// porque NOISE_PATTERNS borra ~ | / como decorado y se lleva el separador puesto.
const SEP = /\s+[-–—~|/]\s+/
// misma idea sin espacios alrededor: "横山みゆき/Miyuki Second"
const TIGHT_SEP = /\s*[/|]\s*/

export function cleanTitle(raw: string): string {
  let s = raw
  for (const p of NOISE_PATTERNS) s = s.replace(p, ' ')
  return s.trim().replace(/\s{2,}/g, ' ')
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
  const parts = raw.split(SEP)
  if (parts.length >= 2) {
    const artist = cleanTitle(parts[0])
    const title = cleanTitle(dropTrailingMeta(parts.slice(1)).join(' - '))
    if (artist && title) return { artist, title }
  }

  const tight = raw.split(TIGHT_SEP)
  if (tight.length === 2) {
    const artist = cleanTitle(tight[0])
    const title = cleanTitle(tight[1])
    // el mínimo evita partir cosas como "AC/DC" cuando no hay separador real
    if (artist.length >= 3 && title.length >= 3) return { artist, title }
  }

  return { title: cleanTitle(raw) }
}

/**
 * Saca los segmentos finales que son metadata y no parte del título:
 * "Miracle Touch - 1986 - Japan" → "Miracle Touch". Los diggers los cuelgan
 * al final separados igual que el artista, así que el split se los lleva.
 */
const TRAILING_META = /^(19[2-9]\d|20[0-2]\d|japan|usa|uk|brazil|brasil|france|italy|germany|jp|us|full album|lp|ep|vinyl)$/i

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
