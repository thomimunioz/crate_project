/**
 * Cliente del backend FastAPI: proxy (CORS/scraping), discovery sin quota
 * (yt-dlp) y análisis de audio (DSP opt-in).
 * En dev, VITE_API_BASE = /api y Vite lo proxea a http://localhost:8787.
 *
 * Regla de la casa: el backend devuelve EVIDENCIA y errores legibles; lo que
 * se decide con esa evidencia (plegar la octava, descartar basura, rankear) es
 * dominio y corre en el cliente.
 */
// `?.`: fuera de Vite (harness con tsx) `import.meta.env` no existe; ahí un
// script puede apuntar al backend con CRATE_API_BASE en el entorno de Node.
const API_BASE =
  import.meta.env?.VITE_API_BASE ||
  (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env?.CRATE_API_BASE ||
  '/api'

/**
 * Error del backend con el `detail` que manda FastAPI. Los códigos importan:
 * 503 = falta toolchain (node/ffmpeg/yt-dlp viejo: el texto dice cómo arreglarlo),
 * 404 = el video/playlist/canal no está disponible, 400 = referencia inválida,
 * 502 = falló la red o yt-dlp. `reachable` = false cuando ni siquiera hubo respuesta.
 */
export class BackendError extends Error {
  readonly status: number
  readonly detail: string
  readonly reachable: boolean

  constructor(status: number, detail: string, reachable = true) {
    super(detail)
    this.name = 'BackendError'
    this.status = status
    this.detail = detail
    this.reachable = reachable
  }

  get kind(): 'toolchain' | 'unavailable' | 'bad_request' | 'unreachable' | 'other' {
    if (!this.reachable) return 'unreachable'
    if (this.status === 503) return 'toolchain'
    if (this.status === 404) return 'unavailable'
    if (this.status === 400 || this.status === 422) return 'bad_request'
    return 'other'
  }
}

/** Lee el `detail` de una respuesta fallida y lo convierte en BackendError. */
async function fallo(res: Response, que: string): Promise<BackendError> {
  const cuerpo = (await res.json().catch(() => null)) as { detail?: unknown } | null
  const detail =
    typeof cuerpo?.detail === 'string'
      ? cuerpo.detail
      : cuerpo?.detail != null
        ? JSON.stringify(cuerpo.detail)
        : `${que} ${res.status}`
  return new BackendError(res.status, detail)
}

/** fetch que distingue "el backend no está" de "el backend dijo que no". */
async function pedir(input: string, init?: RequestInit, que = 'backend'): Promise<Response> {
  let res: Response
  try {
    res = await fetch(input, init)
  } catch (e) {
    throw new BackendError(0, `no se pudo hablar con el backend (${que}): ${e instanceof Error ? e.message : String(e)}`, false)
  }
  if (!res.ok) throw await fallo(res, que)
  return res
}

/** GET a través del proxy con allowlist (para fuentes que CORS bloquea). */
export async function proxyGet<T = unknown>(url: string): Promise<T> {
  const res = await pedir(`${API_BASE}/proxy?url=${encodeURIComponent(url)}`, undefined, `proxy ${url}`)
  return res.json() as Promise<T>
}

// ---------- health ----------

export interface ToolStatus {
  ok: boolean
  version?: string | null
  min?: string | null
  name?: string | null
  path?: string | null
  /** texto accionable de qué falta, o null si está bien */
  problem?: string | null
}

/** Lo que devuelve `ytdl.toolchain()` (contrato C1). Claves extra del backend se ignoran. */
export interface Toolchain {
  ok: boolean
  yt_dlp: ToolStatus
  yt_dlp_ejs?: ToolStatus
  js_runtime: ToolStatus
  ffmpeg: ToolStatus
  fpcalc: ToolStatus
  /** los problemas que impiden bajar y recortar audio; vacío si está todo */
  problems: string[]
}

export interface Health {
  /** se puede bajar y recortar audio: yt-dlp + ejs + runtime JS + ffmpeg */
  ok: boolean
  tools: Toolchain
}

/**
 * `GET /health`. `ok` dice si "Analizar audio" va a andar; `tools.problems`
 * dice qué instalar si no. `refresh` vuelve a mirar el sistema (después de
 * instalar node/ffmpeg con el backend levantado).
 */
export async function health(opts: { refresh?: boolean } = {}): Promise<Health> {
  const res = await pedir(`${API_BASE}/health${opts.refresh ? '?refresh=1' : ''}`, undefined, 'health')
  const data = (await res.json()) as Partial<Health>
  const tools = (data.tools ?? {}) as Partial<Toolchain>
  return {
    ok: Boolean(data.ok),
    tools: {
      ok: Boolean(tools.ok),
      yt_dlp: tools.yt_dlp ?? { ok: false },
      yt_dlp_ejs: tools.yt_dlp_ejs,
      js_runtime: tools.js_runtime ?? { ok: false },
      ffmpeg: tools.ffmpeg ?? { ok: false },
      fpcalc: tools.fpcalc ?? { ok: false },
      problems: Array.isArray(tools.problems) ? tools.problems.filter((p): p is string => typeof p === 'string') : [],
    },
  }
}

// ---------- analyze (Capa 2, opt-in) ----------

export interface Confidenced<T> {
  value: T
  confidence: number
}

/** Un candidato de tempo con la evidencia de audio que lo respalda (0..1). */
export interface BpmAlternative {
  value: number
  support: number
}

/** La ventana real que se analizó, en segundos desde el arranque del track. */
export interface BpmWindow {
  start_sec: number
  seconds: number
}

/**
 * BPM elegido por EVIDENCIA de audio, sin prior de gusto (contrato C2).
 * `value` es el candidato con más support; `alternatives` son todos los
 * evaluados (×0.5, ×1, ×2 y los picos de la autocorrelación), ordenados por
 * support, con el ganador incluido; `ambiguous` = los dos mejores están cerca.
 * Quién pliega a la octava del oído es el cliente (`core/tempo.ts`).
 */
export interface BpmResult extends Confidenced<number> {
  alternatives?: BpmAlternative[]
  ambiguous?: boolean
  window?: BpmWindow | null
  /** versión del algoritmo (p.ej. "onset-ac/2"): para saber qué análisis viejos re-correr */
  method?: string
}

export interface AnalyzeResult {
  bpm?: BpmResult | null
  key?: Confidenced<string> | null
  mood?: Confidenced<{ feels: string[]; textures: string[] }> | null
  instruments?: Confidenced<string[]> | null
  /** si se pidió `identify`, la huella con la misma descarga */
  identification?: IdentifyResult | null
  identification_error?: string | null
  /** duración del track completo según la fuente: para ubicar la ventana en la UI */
  duration_sec?: number | null
}

/**
 * Dispara el análisis de audio (Capa 2, opt-in).
 *
 * El backend baja el audio entero a un temporal, recorta la ventana con ffmpeg
 * y lo borra: nunca se sirve audio. `startSec` es dónde arranca la ventana;
 * sin él, el backend elige (60 s si dura más de 150 s, si no el 20%): nunca la
 * intro. Los errores llegan con el `detail` del backend: 503 dice qué falta
 * instalar, 404 que el video no está, 502 que falló yt-dlp o la red.
 */
export async function analyzeAudio(
  url: string,
  opts?: { startSec?: number; seconds?: number; identify?: boolean },
): Promise<AnalyzeResult> {
  const res = await pedir(
    `${API_BASE}/analyze`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url,
        start_sec: opts?.startSec,
        seconds: opts?.seconds,
        identify: opts?.identify ?? false,
      }),
    },
    'analyze',
  )
  return res.json() as Promise<AnalyzeResult>
}

export interface IdentifyCandidate {
  acoustid: string
  /** similitud de huella que devuelve AcoustID (0..1) */
  score: number
  /** score ajustado por cuánto audio se pudo huellar */
  confidence: number
  recording_mbid?: string | null
  artist?: string | null
  title?: string | null
  /** álbumes donde aparece la grabación */
  releases: string[]
  duration_sec?: number | null
}

export interface IdentifyResult {
  candidates: IdentifyCandidate[]
  fingerprint_seconds: number
  lookup_duration_sec: number
}

/**
 * Identifica un track por HUELLA ACÚSTICA (Capa 2, opt-in).
 *
 * Es el desempate cuando el texto no alcanza: títulos en kanji o cirílico,
 * títulos sueltos de una palabra, rips sin descripción. No lee el título.
 */
export async function identifyAudio(url: string): Promise<IdentifyResult> {
  const res = await pedir(
    `${API_BASE}/identify`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    },
    'identify',
  )
  return res.json() as Promise<IdentifyResult>
}

// ---------- discover (yt-dlp, 0 quota) ----------

/**
 * Lo mínimo que devuelve yt-dlp en modo flat (contrato C3). Nada acá es una
 * decisión de dominio: el backend no filtra basura ni rankea.
 */
export interface DiscoverItem {
  video_id: string
  title: string
  uploader?: string | null
  channel_id?: string | null
  duration_sec?: number | null
  views?: number | null
  /** playlist/canal traen las views REDONDEADAS (945000, 1700); `ytsearch` exactas */
  views_approx?: boolean
  /** posición 1-based dentro de la playlist/canal; null en búsqueda */
  playlist_index?: number | null
  thumbnail?: string | null
  /** `[Deleted video]` / `[Private video]`: viene marcado, no filtrado */
  unavailable?: boolean
  /** solo `ytsearch`: recorte de la descripción, alcanza para oler un ℗ o un link */
  description_snippet?: string | null
}

/** Una tanda de una playlist o de un canal (`GET /discover/playlist|channel`). */
export interface DiscoverListResult {
  kind: 'playlist' | 'channel'
  /** id de playlist (PL…/UU…) o de canal (UC…) */
  id: string
  title: string
  /** dueño de la playlist / nombre del canal */
  uploader?: string | null
  /** UC… del dueño; null si YouTube no lo expone (playlists personales) */
  channel_id?: string | null
  url?: string | null
  /** cuántos hay en total; null si no se pudo saber (tab de canal sin UU) */
  total?: number | null
  offset: number
  /** desde dónde pedir la próxima tanda; null cuando se terminó */
  next_offset?: number | null
  items: DiscoverItem[]
}

/** Tope del backend por tanda (422 si se pide más). */
export const DISCOVER_LIST_MAX = 500
export const DISCOVER_LIST_DEFAULT = 200

/**
 * Busca en YouTube SIN gastar quota: el backend usa yt-dlp, que habla el mismo
 * InnerTube que el reproductor web. `search.list` cuesta 100 de las 10.000
 * unidades diarias; esto cuesta 0. Devuelve los items enteros (views exactas,
 * duración, uploader, recorte de la descripción): alcanza para buscar sin key
 * o con la quota agotada. La metadata rica se pide después con `videos.list`,
 * que sale 1 unidad cada 50 ids.
 */
export async function discoverSearch(q: string, limit = 50): Promise<DiscoverItem[]> {
  const res = await pedir(`${API_BASE}/discover?q=${encodeURIComponent(q)}&limit=${limit}`, undefined, 'discover')
  const data = (await res.json()) as { items?: DiscoverItem[] }
  return (data.items ?? []).filter((i) => Boolean(i.video_id))
}

/** Solo los ids de `discoverSearch`, para quien no necesite el resto. */
export async function discoverIds(q: string, limit = 50): Promise<string[]> {
  return (await discoverSearch(q, limit)).map((i) => i.video_id)
}

/**
 * Lista una playlist ajena por tandas, sin quota ni API key (yt-dlp flat).
 * Acepta un id pelado (PL…/UU…/OL…) o cualquier URL de YouTube con `?list=`.
 * `next_offset` es el cursor: null cuando se terminó. Playlists privadas o
 * inexistentes vuelven como 404 con el detail del backend.
 */
export async function discoverPlaylist(
  url: string,
  offset = 0,
  limit = DISCOVER_LIST_DEFAULT,
): Promise<DiscoverListResult> {
  const params = new URLSearchParams({ url, offset: String(offset), limit: String(Math.min(limit, DISCOVER_LIST_MAX)) })
  const res = await pedir(`${API_BASE}/discover/playlist?${params.toString()}`, undefined, 'discover/playlist')
  return res.json() as Promise<DiscoverListResult>
}

/**
 * Lista los uploads de un canal por tandas, sin quota ni API key. Acepta UC…,
 * @handle, handle sin arroba o URL de canal (/channel/UC…, /@handle, /c/…,
 * /user/…). El backend lista por la playlist de uploads (UU…), que es la que
 * trae uploader/channel_id en cada entry y el total del canal.
 */
export async function discoverChannel(
  url: string,
  offset = 0,
  limit = DISCOVER_LIST_DEFAULT,
): Promise<DiscoverListResult> {
  const params = new URLSearchParams({ url, offset: String(offset), limit: String(Math.min(limit, DISCOVER_LIST_MAX)) })
  const res = await pedir(`${API_BASE}/discover/channel?${params.toString()}`, undefined, 'discover/channel')
  return res.json() as Promise<DiscoverListResult>
}
