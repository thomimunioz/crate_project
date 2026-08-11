/**
 * Taxonomía cerrada de mood + instrumentos. Chica y a propósito.
 * Ver docs/TAXONOMY.md
 */

export const FEELS = [
  'laid-back',
  'groovy',
  'dreamy',
  'dark',
  'melancholic',
  'uplifting',
  'warm',
  'tense',
] as const
export type Feel = (typeof FEELS)[number]

export const TEXTURES = [
  'dusty',
  'clean',
  'lush',
  'raw',
  'lo-fi',
  'psychedelic',
  'organic',
] as const
export type Texture = (typeof TEXTURES)[number]

export type Energy = 1 | 2 | 3 | 4 | 5

export interface Mood {
  energy?: Energy
  feels: Feel[]
  textures: Texture[]
}

/** Instrumentos que más le importan a un beatmaker (base ampliable). */
export const KEY_INSTRUMENTS = [
  'Rhodes',
  'Wurlitzer',
  'piano',
  'organ',
  'clavinet',
  'synth',
  'guitar',
  'bass',
  'drums',
  'percussion',
  'strings',
  'flute',
  'saxophone',
  'trumpet',
  'trombone',
  'harp',
  'vibraphone',
  'vocals',
  'choir',
  'harpsichord',
] as const
export type Instrument = (typeof KEY_INSTRUMENTS)[number]

// mapeos crudos texto → feel/texture. Punto de partida; score-tuner los afina.
const FEEL_HINTS: Record<Feel, string[]> = {
  'laid-back': ['mellow', 'smooth', 'chill', 'quiet storm', 'lounge', 'easy'],
  groovy: ['funk', 'boogie', 'disco', 'groove', 'break'],
  dreamy: ['dream', 'ethereal', 'ambient', 'floating', 'hazy'],
  dark: ['dark', 'noir', 'sinister', 'minor', 'moody'],
  melancholic: ['melanch', 'sad', 'bittersweet', 'nostalg', 'longing', 'blue'],
  uplifting: ['uplift', 'joy', 'sunny', 'gospel', 'bright'],
  warm: ['warm', 'soul', 'tender', 'sweet'],
  tense: ['tense', 'suspense', 'urgent', 'dramatic'],
}

const TEXTURE_HINTS: Record<Texture, string[]> = {
  dusty: ['dusty', 'vinyl', 'crackle', 'old', 'vintage'],
  clean: ['clean', 'hi-fi', 'crisp', 'pristine'],
  lush: ['lush', 'orchestr', 'strings', 'sweeping'],
  raw: ['raw', 'garage', 'rough', 'demo'],
  'lo-fi': ['lo-fi', 'lofi', 'tape', 'cassette'],
  psychedelic: ['psych', 'acid', 'trippy', 'phaser'],
  organic: ['acoustic', 'live', 'organic', 'analog'],
}

/** Inferencia barata de mood a partir de texto (título+desc+tags) y géneros. */
/**
 * Palabras que aparecen en nombres de género. Sirven para reconocer cuando un
 * uploader las cuelga al final del título ("Distances [Haiti] Jazz, Soul,
 * Balearic Fusion"), que es costumbre en los canales de digging.
 * No es una taxonomía: es vocabulario para limpiar texto.
 */
export const GENRE_WORDS: ReadonlySet<string> = new Set([
  'jazz', 'soul', 'funk', 'funky', 'rock', 'pop', 'fusion', 'disco', 'boogie',
  'samba', 'mpb', 'bossa', 'nova', 'library', 'ambient', 'easy', 'listening',
  'balearic', 'folk', 'blues', 'latin', 'brasil', 'brazil', 'brazilian',
  'japanese', 'city', 'aor', 'rare', 'groove', 'grooves', 'breaks', 'psych',
  'psychedelic', 'prog', 'progressive', 'electronic', 'synth', 'wave', 'lounge',
  'cinematic', 'soundtrack', 'ost', 'gospel', 'reggae', 'afro', 'spiritual',
  'modal', 'hammond', 'quiet', 'storm', 'smooth', 'downtempo', 'trip', 'hop',
])

export function inferMoodFromText(text: string, genres: string[] = []): Mood {
  const hay = `${text} ${genres.join(' ')}`.toLowerCase()
  const feels = (Object.keys(FEEL_HINTS) as Feel[]).filter((f) =>
    FEEL_HINTS[f].some((h) => hay.includes(h)),
  )
  const textures = (Object.keys(TEXTURE_HINTS) as Texture[]).filter((t) =>
    TEXTURE_HINTS[t].some((h) => hay.includes(h)),
  )
  return { feels, textures }
}

/** Detecta instrumentos mencionados en texto libre (título/tags). */
export function instrumentsFromText(text: string): Instrument[] {
  const hay = text.toLowerCase()
  return KEY_INSTRUMENTS.filter((i) => hay.includes(i.toLowerCase()))
}
