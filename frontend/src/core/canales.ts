/**
 * Canales — inteligencia de digging en datos, como `scenes.ts`.
 *
 * Un canal de YouTube dice algo de la FUENTE, nunca de la obra: que "Music for
 * empty rooms" haya subido un tema no lo hace más raro ni más escondido, dice
 * que alguien con oído ya lo eligió. Por eso esta lista entra solo a
 * `sourceQualityScore` (con razón: "subido por un curador que ya te dio N
 * temas") y a la semilla de Vetas. NO entra a obscurity ni a rarity
 * (CLAUDE.md: "Rarity ≠ Obscurity ≠ Discovery value — no las colapses").
 *
 * Dos roles:
 *
 *   - `curador`: canales digger de soul/jazz/city pop raro. Semilla: el
 *     benchmark del 19-sep-2026 (`docs/benchmarks/2026-09-19-digging-a-mano/
 *     canales.json`), donde 4 canales concentran lo guardado, más la lista del
 *     brief. `guardados` es lo que Thomas guardó de ese canal ese día: es un
 *     DATO de partida para la affinity, no una regla.
 *   - `ruido`: canales que para ESTE oído no sirven (covers de videojuegos,
 *     OST de anime). Es gusto personal, así que no va en `esBasura` (que es
 *     universal): lo aplica la affinity como peso negativo. Otro beatmaker
 *     puede querer justo eso.
 *
 * Los ids se resolvieron del pool del benchmark. Los nombres cambian
 * ("BigPeter86" / "BigPeter1027" / "BigPeter1086"), los ids no: cuando hay id,
 * manda el id. Nunca se usa esta lista para CONFIRMAR una obra.
 *
 * Mantenimiento: crate-scout, junto a `scenes.ts`.
 */
import type { SceneId } from './scenes'

export type RolDeCanal = 'curador' | 'ruido'

export interface Canal {
  /** id de canal de YouTube (UC…). Si está, manda sobre el nombre. */
  channelId?: string
  nombre: string
  rol: RolDeCanal
  /** escenas en las que el canal rinde; orienta la semilla de Vetas */
  escenas?: SceneId[]
  nota?: string
  /**
   * Prefijo normalizado para familias de canales con el mismo dueño y nombres
   * cambiantes. Se compara con `startsWith`, así que tiene que ser largo y
   * específico ("bigpeter"), nunca una palabra común.
   */
  prefijo?: string
  /** temas guardados de este canal en el benchmark del 19-sep-2026 */
  guardados?: number
}

export const CANALES: Canal[] = [
  // ---- curadores: los que concentraron lo guardado el 19-sep ----
  {
    channelId: 'UCY8_y20lxQhhBe8GZl5A9rw',
    nombre: 'Music for empty rooms',
    rol: 'curador',
    escenas: ['soul-jazz', 'library', 'jazz-fusion', 'city-pop', 'mpb'],
    nota: 'titula "Artista - Título [País] Género, Género (Año)"; 41 en el pool, 6 guardados',
    guardados: 6,
  },
  {
    channelId: 'UC47qc6t2RelhfvI-OjgIY2A',
    nombre: 'Rare Samples & Songs Oleg Tsoy',
    rol: 'curador',
    escenas: ['deep-soul-70s', 'modern-soul', 'soul-jazz'],
    nota: '44 en el pool, 4 guardados',
    guardados: 4,
  },
  {
    channelId: 'UCE-O0L9EzmoEcM69E3QjGTg',
    nombre: 'TheRAREGROOVEMAN',
    rol: 'curador',
    escenas: ['modern-soul', 'deep-soul-70s'],
    nota: 'titula "ARTISTA   TÍTULO" con 2+ espacios como separador',
    guardados: 3,
  },
  {
    channelId: 'UCTFuQaZ4XJ0jQO1MJ4dYFXw',
    nombre: 'si',
    rol: 'curador',
    escenas: ['quiet-storm', 'modern-soul'],
    nota: '"Artista - Título (1984)" y link a Discogs en la descripción; 3 de 3 guardados',
    guardados: 3,
  },
  {
    channelId: 'UCiMAhn-OD_XA8T_reQMcwMA',
    nombre: 'Soultwinz',
    rol: 'curador',
    escenas: ['modern-soul', 'quiet-storm', 'deep-soul-70s'],
    guardados: 2,
  },
  {
    channelId: 'UC546_voUGtgQr5LmtWV-4pQ',
    nombre: 'Winta Groove',
    rol: 'curador',
    escenas: ['modern-soul', 'quiet-storm'],
    guardados: 2,
  },
  {
    channelId: 'UCv5OAW45h67CJEY6kJLyisg',
    nombre: 'André Navarro II',
    rol: 'curador',
    escenas: ['library', 'italian-ost', 'jazz-fusion'],
    nota: 'el que más aportó al pool (54); mucho OST japonés y library',
    guardados: 1,
  },
  { channelId: 'UC1r_Q42GyLb2I1mL0L1Mxqw', nombre: 'skeenery', rol: 'curador', guardados: 1 },
  { channelId: 'UCYPltVawiS_dVsyv13hERgw', nombre: 'Neglected Trax', rol: 'curador', escenas: ['modern-soul'], guardados: 1 },
  {
    channelId: 'UCXV_UkAxldqySLJ-FNqFnCA',
    nombre: 'Casen Fike',
    rol: 'curador',
    escenas: ['deep-soul-70s'],
    nota: 'titula "Artista   Título   1981  Soul Sample"',
    guardados: 1,
  },
  { channelId: 'UCr79VNMYJiZCIUrBt9le6kQ', nombre: 'JazzManDean', rol: 'curador', escenas: ['soul-jazz', 'jazz-fusion'], guardados: 1 },
  { channelId: 'UC8U4Px_RbJat4_4LKJ7n2bw', nombre: 'mikeejaylovessoul', rol: 'curador', escenas: ['modern-soul'], guardados: 1 },
  { channelId: 'UC2xLCkq2twf355YoQggRTyQ', nombre: 'foreal', rol: 'curador', escenas: ['library', 'city-pop'], guardados: 1 },
  {
    channelId: 'UC4rdJibQ4NfeJxGbg4rvNxw',
    nombre: 'ants kask',
    rol: 'curador',
    escenas: ['city-pop', 'wamono-jazz'],
    nota: 'titula "Artista - Título - 1982 - Japan"',
    guardados: 1,
  },
  { channelId: 'UCEiSkaHC2pejVpfC90jeANg', nombre: 'Krem Soulz', rol: 'curador', escenas: ['modern-soul'], guardados: 1 },
  { channelId: 'UC8miJX57wgdexh0Wb7z8wBA', nombre: 'Five Special Records', rol: 'curador', escenas: ['modern-soul'], guardados: 1 },
  {
    channelId: 'UCEfDmBvn1UduuZ84xHB09lQ',
    nombre: 'Athens of The North',
    rol: 'curador',
    escenas: ['modern-soul', 'deep-soul-70s'],
    nota: 'sello de reediciones: el ℗ de sus Topic es el de la reedición',
    guardados: 1,
  },
  {
    channelId: 'UCL8EjPRV5WxrpzU4vn7j8eQ',
    nombre: 'BigPeter1027 Real Music Channel',
    rol: 'curador',
    prefijo: 'bigpeter',
    escenas: ['modern-soul', 'quiet-storm'],
    guardados: 1,
  },
  { channelId: 'UCOXJbiOyAdMleqq7WfU_rzg', nombre: 'BigPeter86 Real Music Channel', rol: 'curador', prefijo: 'bigpeter' },
  { nombre: 'BigPeter1086 Real Music Channel', rol: 'curador', prefijo: 'bigpeter' },

  // ---- curadores del brief que en el pool no llegaron a guardado (o no estaban) ----
  {
    channelId: 'UCKydEBEvAU5zkN8o1snt62A',
    nombre: 'Vinyle Archéologie',
    rol: 'curador',
    escenas: ['city-pop', 'wamono-jazz', 'french-groove'],
    nota: '44 en el pool, 2 sugeridos, 0 guardados: rinde menos para este oído',
  },
  { channelId: 'UCbg_EpZE7JusyO-NNfaZL1Q', nombre: 'Brazilian Nuggets', rol: 'curador', escenas: ['mpb', 'samba-jazz', 'brazilian-soul'] },
  { channelId: 'UCgIpEsSnc-Q7da13qvKS0nw', nombre: 'Obscure Samples', rol: 'curador', escenas: ['deep-soul-70s', 'soul-jazz'] },
  { channelId: 'UCWyd-ogtSjVTusWg9jW3PeQ', nombre: 'lexingtunes', rol: 'curador', escenas: ['deep-soul-70s'] },
  {
    channelId: 'UCXsUJJRPM6MH6THupbN6D_A',
    nombre: "AUGUSTA GA 60'S  and Other States Plus",
    rol: 'curador',
    prefijo: 'augusta ga',
    escenas: ['deep-soul-70s'],
    nota: 'titula "Artista   Título" con 2+ espacios',
  },
  { channelId: 'UC9GAW3RXJxwd1CbWdx78CqA', nombre: 'SOULKATA', rol: 'curador', escenas: ['deep-soul-70s'] },
  { channelId: 'UCdFIdoB4JbFZ7xKu0iQITwQ', nombre: 'Terrestrial Funk', rol: 'curador', escenas: ['modern-soul'], nota: 'sello de reediciones' },
  { channelId: 'UCnJAGiKCR4sk_FL9WuLGoWw', nombre: 'Boca Do Sol', rol: 'curador', escenas: ['mpb', 'brazilian-soul'] },
  { channelId: 'UCujpBBVlcHr0OECaIYtdeeA', nombre: '曲', rol: 'curador', escenas: ['city-pop', 'wamono-jazz'] },
  { channelId: 'UC2MWmQ1_zqnxOvLkvEfaVDQ', nombre: 'Inspiration in sound', rol: 'curador', escenas: ['modern-soul'] },
  {
    channelId: 'UCT_v62A-rWqmhWFE-axqOpg',
    nombre: 'Late Night Quiet Storm Ballad Music Channel',
    rol: 'curador',
    escenas: ['quiet-storm'],
  },
  { channelId: 'UCVuAPMspXqRMqFkcDlmNt3g', nombre: 'DJSoul832', rol: 'curador', escenas: ['modern-soul', 'quiet-storm'] },
  {
    channelId: 'UCoofvCL9BkLti2PIZnD1XdQ',
    nombre: 'Crackle Journey',
    rol: 'curador',
    escenas: ['jazz-fusion', 'soul-jazz'],
    nota: 'titula "Artista - Título [Género] (1980 - País)"',
  },
  {
    channelId: 'UCL2fWywsMWdeckCqrlnVYjQ',
    nombre: 'Antonio Pérez (curated by)',
    rol: 'curador',
    prefijo: 'antonio perez',
    escenas: ['library'],
    nota: 'titula "(Library, 1980)"',
  },
  { nombre: 'Sample Soul 70', rol: 'curador', escenas: ['deep-soul-70s', 'modern-soul'], nota: 'titula "Artista – Título (1975)", a veces con emojis' },
  { nombre: 'Portal Records', rol: 'curador', escenas: ['modern-soul'] },
  { nombre: 'Family Old School Music', rol: 'curador', escenas: ['quiet-storm', 'modern-soul'] },
  { nombre: 'My Vinyl Collection', rol: 'curador', nota: 'titula "Artista - Álbum (1983) - A3 - Título"' },

  // ---- ruido PERSONAL (no universal): lo aplica la affinity, no esBasura ----
  {
    channelId: 'UChkiL7Q3d6I7gdgs34pYGHw',
    nombre: 'The Consouls',
    rol: 'ruido',
    nota: 'covers jazz/funk de videojuegos (Persona, Minecraft, Yakuza); 10 en el pool, 0 guardados',
  },
  { channelId: 'UCPYonkD8SmZdCgYuF1rOmGg', nombre: 'Antoko-rippa ꕥ Sakura Memories!', rol: 'ruido', nota: 'OST de Cardcaptor Sakura' },
  { channelId: 'UCu4-EAWu1YapK2lxRopIkXA', nombre: 'SpyroulGaming', rol: 'ruido', nota: 'OST de Naruto' },
  { channelId: 'UCUXoQXg82MM1p7iR8_V5NxA', nombre: 'TURNERA0921', rol: 'ruido', nota: 'OST de Naruto' },
  { channelId: 'UCn29Ciutzvvo6tPNyRnS_fg', nombre: 'SteelixofGold', rol: 'ruido', nota: 'OST de Naruto' },
  { channelId: 'UC6Z4ib5m6MgTUSWu2qDzoNw', nombre: 'Jorge Lopez', rol: 'ruido', nota: 'OST de Naruto' },
  { channelId: 'UC7HdD_yZgTLUK_EXMYjOUsA', nombre: 'Dahkittydoonsta', rol: 'ruido', nota: 'archivos de sonido de Half-Life' },
  { channelId: 'UCVFq__P1k2FdR3n3cnrmVVg', nombre: 'Batter Montague (The Batter)', rol: 'ruido', nota: 'OST de Yume 2kki' },
  { channelId: 'UCe3G1_BGB0SlJXjgG2t74Tg', nombre: 'Sanji1000', rol: 'ruido', nota: 'OST de Gundam' },
  { channelId: 'UCoE57VNZYxn5f9IhQv7g31g', nombre: 'Musica Karaoke', rol: 'ruido', nota: 'karaoke (además lo corta esBasura)' },
]

/**
 * Temas de videojuegos/anime que para este oído son ruido aunque el canal sea
 * nuevo. Es vocabulario PERSONAL: la affinity lo usa como peso negativo, no es
 * basura universal ("OST" solo NO está acá a propósito: Lupin III o Bruno
 * Nicolai son oro).
 *
 * Todo anclado por palabra entera: sin `\b`, "persona q" pegaba en "Esa persona
 * que amo" (balada latina, escena en alcance) y "zelda" adentro de "Zelda
 * Barron". Los términos que son también nombres de artista piden contexto de
 * juego ("Legend of Zelda", "Zelda … OST/cover") o excluyen la banda real
 * ("The Future Funk Band", 1979). Medido en el pool del 19-sep: los mismos 19
 * items que antes, y 0 guardados/sugeridos (lo chequea `hintsHarness`).
 */
export const TEMAS_DE_RUIDO_PERSONAL =
  /\b(?:naruto|persona\s?(?:[1-5]|q\d?)\b|gundam|cardcaptor|yume 2kki|half[- ]life\b|minecraft|(?:legend of )?zelda(?=\b.*\b(?:ost|theme|lullaby|lo-?fi|cover|remix|medley|bgm|soundtrack|ocarina|majora|wind waker|twilight princess|breath of the wild)\b)|final fantasy|pok[eé]mon|sword art online|code geass|pilotwings|gran turismo|evangelion|ultimate ninja|character select|street fighter|yakuza\s?\d|undertale|touhou|vaporwave|future funk(?! band))\b/i

const normalizar = (s: string): string =>
  s
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim()

const porId = new Map<string, Canal>()
const porNombre = new Map<string, Canal>()
const conPrefijo: Canal[] = []

/**
 * (Re)arma los índices de búsqueda sobre una lista. La app usa `CANALES`
 * siempre; los benchmarks la llaman con una lista recortada para medir sin las
 * entradas que se sembraron desde el mismo benchmark (`guardados` / ruido del
 * pool), que si no son circulares. Llamarla sin argumento restaura la lista.
 */
export function indexarCanales(lista: Canal[] = CANALES): void {
  porId.clear()
  porNombre.clear()
  conPrefijo.length = 0
  for (const c of lista) {
    if (c.channelId) porId.set(c.channelId, c)
    porNombre.set(normalizar(c.nombre), c)
    if (c.prefijo) conPrefijo.push(c)
  }
}
indexarCanales()

/**
 * Busca el canal en la lista: primero por id (estable), después por nombre
 * exacto normalizado, después por prefijo de familia. Devuelve undefined si no
 * lo conocemos — que es lo normal, y no dice nada malo del canal.
 */
export function canalDe(channelId?: string, uploader?: string): Canal | undefined {
  if (channelId) {
    const c = porId.get(channelId)
    if (c) return c
  }
  if (!uploader) return undefined
  const n = normalizar(uploader)
  if (!n) return undefined
  const exacto = porNombre.get(n)
  if (exacto) return exacto
  return conPrefijo.find((c) => n.startsWith(c.prefijo as string))
}

/** Atajo para el score y la UI: ¿este canal ya demostró tener oído? */
export function esCurador(channelId?: string, uploader?: string): boolean {
  return canalDe(channelId, uploader)?.rol === 'curador'
}
