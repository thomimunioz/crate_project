/**
 * Fan-out de queries de descubrimiento — donde el producto vive o muere.
 *
 * Traduce un `SearchQuery` a un abanico de queries concretas para YouTube, y
 * después ordena lo que vuelve para que arriba quede lo que un digger se
 * llevaría. Son dos mitades del mismo problema:
 *
 *   1. `planificarQueries` — qué preguntar (y qué NO preguntar).
 *   2. `esBasura` + `ordenarParaDigging` — qué merece que gastemos enrichment.
 *
 * ## Lo que se midió contra la API (agosto 2026, 9 sondas de 50 resultados)
 *
 * | query                                          | mediana views | <1k |
 * |------------------------------------------------|--------------:|----:|
 * | `japanese city pop 1982` (literal)              |       177.980 |   1 |
 * | `japanese city pop 1982 vinyl rip`              |       124.708 |   2 |
 * | `シティポップ 1982 アルバム` (nativo)              |         1.184 |  25 |
 * | `"Alfa Records" 1982 vinyl LP` (sello)          |         1.841 |  17 |
 * | `MPB 1974 disco completo vinil raro` (nativo)   |         1.115 |  22 |
 * | `modern soul boogie 1982 LP private press`      |           806 |  32 |
 * | `KPM library music 1974 LP` (sello)             |           273 |  33 |
 *
 * Tres conclusiones, y las tres están cableadas acá:
 *
 * - **Decorar no sirve.** Agregarle "vinyl rip" a un término popular no lo baja
 *   de nivel: el término popular manda igual. Hay que cambiar el SUSTANTIVO —
 *   el sello, la jerga, el idioma, un artista de segunda línea.
 * - **La query literal es carnada de mixes.** Por eso, cuando se reconoce la
 *   escena, la literal no se dispara: no vale 100 unidades de quota.
 * - **Más de 4 tokens raros juntos ahoga la búsqueda.** `Piero Umiliani
 *   sonorizzazioni 1974 LP` devolvió 13 resultados de 50 posibles. Cada lane
 *   arma 3–5 tokens, no más.
 *
 * ## Quota
 *
 * `search.list` cuesta 100 unidades y **cuesta lo mismo con maxResults=50 que
 * con 20**, así que siempre se piden 50. `videos.list` cuesta 1 cada 50 ids.
 * Con el presupuesto por defecto (3 búsquedas): 3×100 + 3×1 = **303 unidades**
 * por búsqueda del usuario → ~33 búsquedas por día. Ver docs/SOURCES.md.
 */
import type { SearchQuery, SourceItem } from './entities'
import type { Escena, SceneId } from './scenes'
import { detectarEscenas } from './scenes'
import { cleanTitle } from './fuzzy'

// ---------- tipos ----------

/**
 * Estrategia de una query. Cada lane ataca el long tail por un lado distinto;
 * el orden de este tipo es el orden de prioridad medido.
 */
export type Lane = 'jerga' | 'sello' | 'nativo' | 'artista' | 'descriptor' | 'literal'

export interface DiggerQuery {
  /** el string que va a `search.list` */
  q: string
  lane: Lane
  escena?: SceneId
  /** para el log y para depurar el plan: por qué se eligió */
  porQue: string
}

export interface PlanDeDigging {
  queries: DiggerQuery[]
  escenas: SceneId[]
  /** ventana de años con la que se armaron las queries */
  epoca?: [number, number]
  /** el año concreto que se usó (uno solo: los rips se titulan con el año) */
  anio?: number
  /** costo del plan en unidades de quota, contando el videos.list de stats */
  costoUnidades: number
}

export interface OpcionesDePlan {
  /** cuántos `search.list` gastar. Default 3 (303 unidades). */
  presupuesto?: number
  /**
   * Semilla de la rotación. Por defecto cambia por día: la misma búsqueda
   * mañana explora otros sellos y otros artistas de la misma escena, que es
   * lo que hace que el crate crezca en vez de repetirse.
   */
  semilla?: number
}

export const PRESUPUESTO_POR_DEFECTO = 3
export const COSTO_SEARCH_LIST = 100
export const COSTO_VIDEOS_LIST = 1
/** search.list cobra 100 unidades igual con 5 que con 50: siempre pedimos 50. */
export const MAX_RESULTS_POR_BUSQUEDA = 50

// ---------- azar reproducible ----------

function hashTexto(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

/** mulberry32: chico, determinista y suficiente para rotar listas. */
function azar(semilla: number): () => number {
  let a = semilla >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/**
 * Elige sesgado hacia el principio de la lista. Las listas de `scenes.ts` están
 * ordenadas de más a menos canónico: el sello grande de la escena rinde más que
 * el último de la lista, pero el último tiene que salir a veces o no exploramos
 * nada. El exponente inclina la moneda sin cerrar la puerta.
 *
 * Con 2.2, sobre una lista de 5 el primero sale ~48% de las veces y sobre una
 * de 17 el primero sale ~27%. Se subió de 1.7 después de ver una corrida donde
 * la rotación eligió dos términos flojos seguidos para city pop y la búsqueda
 * entera se fue a enka de los 50.
 */
const SESGO_A_LA_CABEZA = 2.2

function elegir<T>(lista: readonly T[], cuantos: number, rnd: () => number): T[] {
  if (lista.length <= cuantos) return [...lista]
  const copia = [...lista]
  const out: T[] = []
  for (let i = 0; i < cuantos && copia.length; i++) {
    const idx = Math.floor(Math.pow(rnd(), SESGO_A_LA_CABEZA) * copia.length)
    out.push(copia.splice(idx, 1)[0])
  }
  return out
}

/**
 * Junta los pedazos de una query sacando palabras repetidas.
 *
 * Sin esto salen cosas como `clube da esquina brazil groove LP 1973 LP`: la
 * jerga ya trae "LP" adentro y el formato lo agrega de nuevo. YouTube trata
 * cada token como un AND, así que repetir no suma y encima gasta relevancia.
 */
function armarQuery(...pedazos: Array<string | undefined>): string {
  const vistas = new Set<string>()
  const salida: string[] = []
  for (const pedazo of pedazos) {
    if (!pedazo) continue
    const tokens = pedazo.split(/\s+/).filter(Boolean)
    const claves = tokens.map((t) => t.toLowerCase().replace(/["']/g, ''))
    // El pedazo entra entero o no entra: dejar "disco" suelto porque "completo"
    // ya estaba es peor que no agregar nada.
    if (claves.some((k) => vistas.has(k))) continue
    for (const k of claves) vistas.add(k)
    salida.push(...tokens)
  }
  return salida.join(' ')
}

/** Formatos de rip, para rotar el cierre de las queries entre búsquedas. */
const CIERRES = ['LP', 'vinyl LP', 'LP full album', 'private press LP'] as const

// ---------- época ----------

const RE_ANIO = /\b(19[2-9]\d|20[0-2]\d)\b/
const RE_DECADA = /\b(?:19)?([2-9]0)['´]?s\b/i

/**
 * Saca año o década del pedido. Un año CONCRETO vale mucho más que una década:
 * los rips se titulan "(1974)", casi nunca "70s", así que "MPB 1974" cae en
 * títulos de rip y "MPB 70s" cae en playlists.
 */
export function detectarEpoca(q: SearchQuery): { rango?: [number, number]; anio?: number } {
  if (q.year) {
    const [a, b] = q.year
    return { rango: [a, b], anio: a === b ? a : undefined }
  }
  const anio = q.text.match(RE_ANIO)
  if (anio) return { rango: [Number(anio[1]), Number(anio[1])], anio: Number(anio[1]) }

  const dec = q.text.match(RE_DECADA)
  if (dec) {
    const dd = Number(dec[1])
    const base = dd >= 20 && dd <= 90 ? 1900 + dd : 1970
    return { rango: [base, base + 9] }
  }
  return {}
}

/** Intersección de la ventana pedida con la ventana buena de la escena. */
function ventana(escena: Escena | undefined, pedido?: [number, number]): [number, number] {
  const propia = escena?.epoca ?? [1968, 1988]
  if (!pedido) return propia
  const lo = Math.max(propia[0], pedido[0])
  const hi = Math.min(propia[1], pedido[1])
  return lo <= hi ? [lo, hi] : pedido
}

// ---------- armado de queries ----------

const comillas = (s: string): string => (s.includes(' ') ? `"${s}"` : s)

/**
 * La query vieja: concatenar texto + géneros + instrumentos. Se mantiene como
 * fallback y como línea de base para medir. Ver la tabla de arriba para lo que
 * rinde: es exactamente el "500 temas genéricos" del CLAUDE.md.
 */
export function queryLiteral(q: SearchQuery): string {
  const extra: string[] = []
  if (q.genres?.length) extra.push(q.genres.join(' '))
  if (q.instruments?.length) extra.push(q.instruments.join(' '))
  return [q.text, ...extra].filter(Boolean).join(' ').trim()
}

/** Sin escena reconocida no hay sellos ni jerga: se decora el texto del usuario. */
function planFallback(q: SearchQuery, anio: number | undefined, rnd: () => number): DiggerQuery[] {
  const base = queryLiteral(q)
  const sufijos: Array<[string, string]> = [
    ['LP full album', 'formato de disco entero'],
    ['vinyl rip rare obscure', 'vocabulario de rip y de rareza'],
    [anio ? `${anio} vinyl LP` : 'private press LP', 'año concreto o prensado propio'],
    ['45 7" rare groove', 'simples, que casi nunca están en playlists'],
  ]
  return elegir(sufijos, 4, rnd).map(([sufijo, porQue]) => ({
    q: `${base} ${sufijo}`.trim(),
    lane: 'literal' as Lane,
    porQue: `sin escena reconocida — ${porQue}`,
  }))
}

/**
 * Arma el abanico. Devuelve las queries YA priorizadas y recortadas al
 * presupuesto: quien llama solo tiene que ejecutarlas.
 */
export function planificarQueries(q: SearchQuery, opts: OpcionesDePlan = {}): PlanDeDigging {
  const presupuesto = Math.max(1, opts.presupuesto ?? PRESUPUESTO_POR_DEFECTO)
  const dia = Math.floor(Date.now() / 86_400_000)
  const rnd = azar(opts.semilla ?? (hashTexto(q.text) ^ dia) >>> 0)

  const escenas = detectarEscenas(q.text, [
    ...(q.genres ?? []),
    ...(q.styles ?? []),
  ])
  const { rango, anio: anioPedido } = detectarEpoca(q)
  const principal = escenas[0]
  const epoca = ventana(principal, rango)

  // Un año concreto y no una década: ver el comentario de `detectarEpoca`.
  // Cuando el usuario no lo fijó, se rota dentro de la ventana buena de la
  // escena, así dos búsquedas iguales en días distintos caen en años distintos.
  const anio = anioPedido ?? epoca[0] + Math.floor(rnd() * (epoca[1] - epoca[0] + 1))

  if (!principal) {
    const queries = planFallback(q, anioPedido, rnd).slice(0, presupuesto)
    return {
      queries,
      escenas: [],
      epoca: rango,
      anio: anioPedido,
      costoUnidades: costoDe(queries.length),
    }
  }

  const candidatas: DiggerQuery[] = []
  const segunda = escenas[1]

  // 0) LO QUE NOMBRÓ EL USUARIO. Si el texto trae un artista o un sello de la
  //    escena, esa es la mejor query que existe y no hay que rotarla: pedir
  //    "minako yoshida" y que el plan salga a buscar a Rajie es un bug, no
  //    exploración. Va primera y se le agrega vocabulario de rip nomás.
  const nombrado = [...principal.artistas, ...principal.sellos].find((n) =>
    q.text.toLowerCase().includes(n.toLowerCase()),
  )
  if (nombrado) {
    candidatas.push({
      q: armarQuery(q.text, 'LP vinyl full album'),
      lane: 'artista',
      escena: principal.id,
      porQue: `lo pediste por nombre (${nombrado})`,
    })
  }
  const cierre = elegir(CIERRES, 1, rnd)[0]
  /** términos ya usados: dos lanes que preguntan lo mismo son 100 unidades tiradas */
  const usados = new Set<string>()
  const libre = (t: string): boolean => !usados.has(t.toLowerCase())
  const marcar = (t: string): void => void usados.add(t.toLowerCase())

  // 1) JERGA — lo medido más fuerte (32/50 abajo de 1000 views). Reemplaza el
  //    nombre popular de la escena por cómo la nombra el que la colecciona.
  //    Un solo término: dos jergas en la misma query se piden con AND y ahogan
  //    la búsqueda (la sonda con 5 tokens raros devolvió 13 resultados de 50).
  const jerga = elegir(principal.jerga, 1, rnd)[0]
  if (jerga) {
    marcar(jerga)
    candidatas.push({
      q: armarQuery(jerga, String(anio), cierre),
      lane: 'jerga',
      escena: principal.id,
      porQue: `jerga de ${principal.nombre} en vez del nombre popular`,
    })
  }

  // 2) SELLO — un sello no lo escribe nadie de paso; además cae mucho canal
  //    "- Topic" (24 de 50 en la sonda), que es metadata de catálogo servida.
  //    Un sello de una sola palabra puede ser ambiguo ("Elenco", "Patchwork"):
  //    se lo acompaña con la jerga de la escena, que es lo que hizo funcionar
  //    `KPM library music 1974 LP` (33 de 50 abajo de 1000 views).
  const desambiguar = principal.jerga.find((j) => j.length <= 18) ?? principal.populares[0]
  for (const sello of elegir(principal.sellos, 2, rnd)) {
    const solaPalabra = !sello.includes(' ')
    candidatas.push({
      q: armarQuery(comillas(sello), String(anio), solaPalabra ? desambiguar : undefined, cierre),
      lane: 'sello',
      escena: principal.id,
      porQue: `sello de la escena (${sello})`,
    })
  }

  // 3) NATIVO — el idioma del lugar filtra solo: en kanji o en portugués no hay
  //    playlists internacionales compitiendo por el ranking.
  if (principal.nativo) {
    const { terminos, formato } = principal.nativo
    const t = elegir(terminos.filter(libre), 1, rnd)[0] ?? terminos[0]
    marcar(t)
    candidatas.push({
      q: armarQuery(t, String(anio), ...elegir(formato, 2, rnd)),
      lane: 'nativo',
      escena: principal.id,
      porQue: `vocabulario en ${principal.nativo.idioma} — sin competencia de playlists`,
    })
  }

  // 4) ARTISTA — el long tail de la escena, rotando. Nunca los `obvios`.
  for (const artista of elegir(principal.artistas, 2, rnd)) {
    candidatas.push({
      q: anioPedido
        ? armarQuery(artista, String(anioPedido), 'LP')
        : armarQuery(artista, 'full album LP'),
      lane: 'artista',
      escena: principal.id,
      porQue: `artista de segunda línea de ${principal.nombre}`,
    })
  }

  // 5) ESCENA HERMANA — cuando el texto pega en dos escenas, una query cruzada
  //    trae el borde entre las dos, que es donde nadie busca.
  if (segunda) {
    const j = elegir(segunda.jerga.filter(libre), 1, rnd)[0]
    if (j) {
      marcar(j)
      candidatas.push({
        q: armarQuery(j, String(anio), 'vinyl'),
        lane: 'jerga',
        escena: segunda.id,
        porQue: `escena hermana (${segunda.nombre})`,
      })
    }
  }

  // 6) DESCRIPTOR — instrumento/mood del pedido. Va último a propósito: los
  //    instrumentos casi nunca están en el título de YouTube, salen de los
  //    créditos de Discogs en el enrichment. Solo entra con presupuesto grande.
  const descriptores = [...(q.instruments ?? []), ...(q.feels ?? [])].slice(0, 2)
  if (descriptores.length) {
    candidatas.push({
      q: armarQuery(descriptores.join(' '), jerga ?? principal.nombre, String(anio), 'LP'),
      lane: 'descriptor',
      escena: principal.id,
      porQue: 'instrumento/mood pedido, por si viene taggeado en el título',
    })
  }

  // Prioridad: jerga → sello → nativo → artista → resto. Se toma una de cada
  // lane antes de repetir lane, así el abanico se abre en vez de profundizar.
  // Si el usuario nombró algo concreto, esa lane arranca; si no, manda la jerga.
  const orden: Lane[] = nombrado
    ? ['artista', 'jerga', 'sello', 'nativo', 'descriptor', 'literal']
    : ['jerga', 'sello', 'nativo', 'artista', 'descriptor', 'literal']
  const porLane = new Map<Lane, DiggerQuery[]>()
  for (const c of candidatas) porLane.set(c.lane, [...(porLane.get(c.lane) ?? []), c])

  const queries: DiggerQuery[] = []
  for (let vuelta = 0; queries.length < presupuesto && vuelta < 4; vuelta++) {
    for (const lane of orden) {
      const cola = porLane.get(lane)
      if (!cola?.length) continue
      queries.push(cola.shift() as DiggerQuery)
      if (queries.length >= presupuesto) break
    }
  }

  return {
    queries,
    escenas: escenas.map((e) => e.id),
    epoca,
    anio,
    costoUnidades: costoDe(queries.length),
  }
}

/** N búsquedas + el videos.list de stats (1 unidad cada 50 ids). */
function costoDe(cantidadDeQueries: number): number {
  return cantidadDeQueries * COSTO_SEARCH_LIST + cantidadDeQueries * COSTO_VIDEOS_LIST
}

// ---------- filtro anti-basura ----------

/**
 * Nada de esto es un disco de otra gente. Se tira sin mirar views.
 *
 * La segunda mitad —VST, kontakt, pianobook, backing tracks— salió de medir:
 * la query literal `library music cinematic strings 1974` devuelve demos de
 * librerías de sample ("Blade Runner Strings FREE Virtual Instruments",
 * "Spitfire Symphonic Strings"). Tienen 300 views y parecen joyas por número,
 * pero son exactamente lo que CLAUDE.md pone fuera del producto.
 */
const BASURA =
  /(type beat|sample pack|sample kit|drum kit|beat tape|karaoke|\breaction\b|\breacts?\b|tutorial|how to make|nightcore|sped ?up|slowed( ?\+ ?reverb)?|8d audio|ai cover|full movie|unboxing|\bhaul\b|virtual instrument|\bvsts?\b|\bkontakt\b|pianobook|spitfire|sample library|\bplugins?\b|preset|backing track|no copyright|free download)/i

/** Vocabulario de mix/playlist. Solo cuenta si además es largo. */
const MIX =
  /(playlist|\bmix\b|mixtape|\bbgm\b|作業用|プレイリスト|セレクション|non ?stop|megamix|dj set|medley|メドレー|best of|greatest hits|top \d+|\d+\s*(hours?|hrs?|horas)|compilation|24\/7|live ?stream|\bradio\b|vol\.? ?\d+)/i

/** Avisos de venta y shorts de tienda de discos: son fotos con música de fondo. */
const VENTA = /(lote\s*\d|à venda|a venda|for sale|disponí|#shorts|#vinylcommunity|garimp|\bmídia\b)/i

/**
 * Videos que HABLAN de discos en vez de pasarlos.
 *
 * Es la basura más difícil de ver: duran 5–20 minutos, tienen el año en el
 * título, 300 views y un canal chico, o sea que puntúan como joya. YouTube
 * japonés y brasileño están llenos ("【音楽解説】1982年のシティ・ポップ", "Mostra LP
 * MPB coleção"). Se cortan en cualquier duración.
 */
const CHARLA =
  /(解説|語る|聴いてみた|レビュー|ランキング|ベスト ?\d+|紹介|開封|ジャケット|mostra lp|coleç|colecc|reseña|\breview\b|unbox|documental|entrevista|interview)/i

/** Jerga de rip: dice "esto salió de un disco físico". */
const JERGA_RIP =
  /(vinyl ?rip|vinil|vinyle|vinilo|vinile|\bLP\b|\bEP\b|\b45\b|\b7"|\b12"|side [ab]\b|lado [ab]\b|full album|álbum completo|album completo|disco completo|album complet|レコード|アルバム|全曲|完全版|private press|test press|original press|\bobi\b|33 tours)/i

const RUIDO_BLANDO = /(\blive\b|lyrics?|subtitulad|\bcover\b|karaoke|remix|instrumental version)/i

const clamp01 = (x: number): number => Math.max(0, Math.min(1, x))

const textoDe = (i: SourceItem): string =>
  `${i.title} ${i.uploader ?? ''} ${(i.tags ?? []).join(' ')}`

/**
 * Descarta lo que no es un disco de otra gente. Es agresivo a propósito: con
 * 3 búsquedas de 50 entran ~150 candidatos y el enrichment solo se come 24, así
 * que tirar de más cuesta poco y tirar de menos llena la lista de mixes.
 */
export function esBasura(item: SourceItem): boolean {
  const dur = item.durationSec ?? 0
  const t = item.title
  const hashtags = (t.match(/#/g) ?? []).length

  if (BASURA.test(textoDe(item))) return true
  if (CHARLA.test(t)) return true
  // 0s = vivo/estreno; menos de 30s no es ni un cue de library
  if (dur > 0 && dur < 30) return true
  if (dur === 0) return true
  // arriba de 75 minutos no existe el LP: es un mix
  if (dur > 4500) return true
  // 15+ minutos con vocabulario de playlist: los canales de "TOKYO 1982
  // 【Playlist 48】" son la mitad de lo que devuelve una query literal
  if (dur > 900 && MIX.test(t)) return true
  if (dur < 150 && (VENTA.test(t) || hashtags >= 3)) return true
  return false
}

// ---------- puntaje de digging (pre-enrichment) ----------

export interface PuntajeDeDig {
  valor: number
  motivos: string[]
}

export interface ContextoDeEscena {
  /** vocabulario de las escenas del plan: sellos, artistas, jerga, términos nativos */
  pertinentes?: string[]
  /** el año con el que se armaron las queries */
  anio?: number
  /** nombres a penalizar */
  obvios?: string[]
}

/**
 * ¿Este resultado es de la escena que se pidió, o se coló?
 *
 * Sin este freno el orden es puro "pocas views" y entra cualquier cosa: medido,
 * la lane `brazilian private press 1973 LP` devolvió private press de Alaska y
 * de Pennsylvania arriba de todo, porque YouTube diluye "brazilian" contra los
 * otros tokens y 157 views siempre gana. Un hallazgo tiene que ser un hallazgo
 * *de lo que buscaste*.
 *
 * Se aplica MULTIPLICANDO, no sumando. Sumándola, un tema conocido de la escena
 * (35.000 views, canal - Topic) le ganaba a un desconocido de la escena, que es
 * exactamente al revés de lo que queremos: la pertinencia es un piso de entrada,
 * la obscuridad sigue siendo el criterio.
 */
function pertinencia(item: SourceItem, ctx: ContextoDeEscena): number {
  const terminos = ctx.pertinentes ?? []
  if (!terminos.length) return 1 // sin escena reconocida no tenemos con qué juzgar

  const hay = ` ${[item.title, item.uploader, (item.tags ?? []).join(' '), (item.description ?? '').slice(0, 400)].join(' ').toLowerCase()} `
  for (const t of terminos) {
    // los términos cortos ("MPB", "CAM") necesitan borde de palabra o matchean cualquier cosa
    if (t.length >= 5 ? hay.includes(t) : hay.includes(` ${t} `)) return 1
  }
  if (ctx.anio != null) {
    for (const m of item.title.matchAll(/\b(19[2-9]\d)\b/g)) {
      if (Math.abs(Number(m[1]) - ctx.anio) <= 2) return 0.75
    }
  }
  return 0.5
}

/**
 * Qué tan "digno de gastar enrichment" es un candidato, con lo único que
 * tenemos antes de cruzar contra catálogo: YouTube.
 *
 * OJO: **esto no es el CRATE Score.** El score se calcula después, con rarity
 * de Discogs y affinity, y es el que ve el usuario (ver docs/CRATE_SCORE.md).
 * Esto es un portero: decide cuáles 24 de los ~150 candidatos se ganan las
 * llamadas a MusicBrainz y Discogs.
 */
export function puntajeDeDig(item: SourceItem, ctx: ContextoDeEscena = {}): PuntajeDeDig {
  const motivos: string[] = []
  const titulo = item.title
  const hay = `${titulo} ${item.description ?? ''}`.toLowerCase()

  const views = item.views ?? 0
  const obscuridad = clamp01(1 - Math.log10(Math.max(views, 10)) / 6)
  if (views > 0 && views < 1000) motivos.push(`${views} views`)

  const dur = item.durationSec ?? 0
  const formato =
    dur >= 90 && dur <= 900 ? 1 : dur >= 30 && dur < 90 ? 0.55 : dur <= 2700 ? 0.55 : 0.25
  if (dur > 900) motivos.push('parece un LP entero')

  let senales = 0
  if (/ - Topic$/.test(item.uploader ?? '')) {
    senales += 0.4
    motivos.push('canal - Topic (metadata del sello)')
  }
  if (/discogs\.com|musicbrainz\.org/i.test(item.description ?? '')) {
    senales += 0.35
    motivos.push('linkea el disco en catálogo')
  }
  if (JERGA_RIP.test(titulo)) {
    senales += 0.2
    motivos.push('titulado como rip de disco')
  }
  if (RE_ANIO.test(titulo)) {
    senales += 0.15
    motivos.push('trae el año en el título')
  }
  if ((item.tags?.length ?? 0) > 0) senales += 0.1

  const pert = pertinencia(item, ctx)
  if (pert <= 0.5) motivos.push('no se le ve nada de la escena pedida')

  let castigo = 0
  const obvio = (ctx.obvios ?? []).find((o) => o.length > 3 && hay.includes(o))
  if (obvio) {
    castigo += 0.35
    motivos.push(`hiper-conocido (${obvio})`)
  }
  if (RUIDO_BLANDO.test(titulo)) castigo += 0.1

  /**
   * Forma del puntaje: `calidad × pertinencia × obscuridad`.
   *
   * Las tres son multiplicativas porque las tres son condiciones necesarias, no
   * méritos que se compensan. Con obscuridad sumando, un tema de 6,7 millones de
   * views subido por un canal "- Topic" entraba igual al top 24: sacaba puntos
   * por metadata perfecta y por durar 3 minutos. Metadata perfecta de algo que
   * ya escuchó todo el mundo no es un hallazgo.
   *
   * El piso de 0.25 evita que un upload nuevo con views bajísimas por edad y no
   * por rareza se lleve todo; el CRATE Score después corrige eso bien, con la
   * antigüedad del upload y el want/have de Discogs.
   */
  const calidad = 0.35 * formato + 0.65 * clamp01(senales)
  const valor = clamp01(calidad * pert * (0.25 + 0.75 * obscuridad) - castigo)
  return { valor, motivos }
}

// ---------- orden final ----------

export interface CandidatoDeDigging {
  item: SourceItem
  lane: Lane
}

/**
 * Clave para reconocer la misma obra subida por canales distintos. Se apoya en
 * `cleanTitle` (que ya saca "[Vinyl Rip]", "(1982)", "HQ" y la lista de géneros
 * colgada al final) y después tira todo lo que no sea letra o número.
 */
function claveDeObra(titulo: string): string {
  const limpio = cleanTitle(titulo)
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, '')
  return limpio || titulo.toLowerCase()
}

export interface OpcionesDeOrden extends ContextoDeEscena {
  /** cuántos temas del mismo canal pueden entrar seguidos. Default 4. */
  topePorCanal?: number
}

/**
 * Puntaje mínimo para entrar al reparto por lane. Calibrado contra la corrida
 * del caso MPB: deja pasar un tema de 35k views con metadata de catálogo (0.29)
 * y frena uno de 348k (0.18) y uno de 6,7M (0.17).
 */
const PISO_DE_CALIDAD = 0.25

/**
 * Ordena para que el pipeline se lleve lo mejor de CADA lane, no lo mejor de
 * una sola.
 *
 * Sin esto, la lane que devuelve views más bajas se come los 24 lugares del
 * enrichment y la búsqueda entera queda con la cara de un solo canal. El
 * round-robin con tope por canal es lo que hace que el resultado se sienta un
 * hallazgo y no un scrape.
 */
export function ordenarParaDigging(
  candidatos: CandidatoDeDigging[],
  opts: OpcionesDeOrden = {},
): SourceItem[] {
  const tope = opts.topePorCanal ?? 4
  const ctx: ContextoDeEscena = {
    obvios: opts.obvios,
    anio: opts.anio,
    // se normaliza una sola vez, no una por candidato
    pertinentes: opts.pertinentes?.map((t) => t.toLowerCase()),
  }

  // Un mismo tema subido por cuatro canales son cuatro slots de enrichment
  // gastados en la misma ficha (medido: "Sylvia Striplin - You Can't Turn Me
  // Away" ocupó 4 de los 24). Se queda el mejor puntuado de cada obra.
  const mejorPorObra = new Map<string, { c: CandidatoDeDigging; p: number }>()
  for (const c of candidatos) {
    const p = puntajeDeDig(c.item, ctx).valor
    const clave = claveDeObra(c.item.title)
    const previo = mejorPorObra.get(clave)
    if (!previo || p > previo.p) mejorPorObra.set(clave, { c, p })
  }

  const porLane = new Map<Lane, Array<{ item: SourceItem; p: number }>>()
  for (const { c, p } of mejorPorObra.values()) {
    porLane.set(c.lane, [...(porLane.get(c.lane) ?? []), { item: c.item, p }])
  }
  for (const cola of porLane.values()) cola.sort((a, b) => b.p - a.p)

  const lanes = [...porLane.keys()]
  const usadoPorCanal = new Map<string, number>()
  const salida: SourceItem[] = []
  const postergados: Array<{ item: SourceItem; p: number }> = []

  let quedan = true
  while (quedan) {
    quedan = false
    for (const lane of lanes) {
      const cola = porLane.get(lane)
      if (!cola?.length) continue
      quedan = true
      const entrada = cola.shift() as { item: SourceItem; p: number }
      const { item, p } = entrada
      // Piso de calidad: el round-robin reparte lugares parejo entre lanes, así
      // que una lane que salió mal metía igual sus 8 mejores. Medido: la lane
      // `Odeon 1973 MPB LP` colaba un tema de 6,7 millones de views en el
      // puesto 13 porque era lo mejor que tenía. Si no llega al piso, espera.
      const canal = item.channelId ?? item.uploader ?? '?'
      const usado = usadoPorCanal.get(canal) ?? 0
      if (p < PISO_DE_CALIDAD || usado >= tope) {
        // nada se pierde: baja al final, para que igual esté si hace falta
        postergados.push(entrada)
        continue
      }
      usadoPorCanal.set(canal, usado + 1)
      salida.push(item)
    }
  }
  postergados.sort((a, b) => b.p - a.p)
  return [...salida, ...postergados.map((x) => x.item)]
}
