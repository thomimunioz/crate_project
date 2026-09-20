/**
 * YouTube — la fuente de descubrimiento principal.
 *
 * Dos caminos, a propósito (ver docs/SOURCES.md y backend/app/discover.py):
 *
 *   - **yt-dlp vía backend, 0 quota**: buscar (`/discover`), listar playlists
 *     y canales enteros por tandas (`/discover/playlist|channel`, flat). Trae
 *     id, título, uploader, channel_id, duración, views REDONDEADAS y miniatura.
 *     No trae descripción, tags ni fecha.
 *   - **Data API v3, con key y quota**: `videos.list` (1 unidad cada 50 ids)
 *     para la metadata rica que alimenta `core/ytHints.ts` (℗, link a Discogs,
 *     tags, fecha). Se pide SOLO para la tanda que se va a enriquecer, nunca
 *     para un pool entero: una veta de 2.000 temas cuesta 40 unidades en total
 *     y 0 hasta que se empieza a cavar.
 *
 * Sin `VITE_YOUTUBE_API_KEY` (o con la quota agotada) la app degrada en vez de
 * tirar: busca, lista y cava igual con lo que trae yt-dlp, con hints más pobres
 * (sin ℗ ni links) y avisando.
 */
import type { SourceItem, SearchQuery } from '@/core/entities'
import type { DiscoverySource } from './types'
import {
  BackendError,
  discoverChannel,
  discoverSearch,
  discoverPlaylist,
  DISCOVER_LIST_DEFAULT,
  type DiscoverItem,
  type DiscoverListResult,
} from '@/api/backend'
import {
  planificarQueries,
  esBasura,
  ordenarParaDigging,
  MAX_RESULTS_POR_BUSQUEDA,
  PRESUPUESTO_POR_DEFECTO,
  type CandidatoDeDigging,
  type DiggerQuery,
  type PlanDeDigging,
} from '@/core/queries'
import { ESCENAS, obviosDe } from '@/core/scenes'

// `?.`: fuera de Vite (harness con tsx) `import.meta.env` no existe
const KEY: string | undefined = import.meta.env?.VITE_YOUTUBE_API_KEY || undefined
const BASE = 'https://www.googleapis.com/youtube/v3'

/** ¿Hay API key? Sin ella se lista y se cava igual, pero sin descripción ni tags. */
export const hayApiKey = (): boolean => Boolean(KEY)

/** Aviso para la UI cuando se busca o se cava sin key (lo que se pierde, no lo que se rompe). */
export const AVISO_SIN_KEY =
  'Sin VITE_YOUTUBE_API_KEY: se busca, se lista y se cava igual (yt-dlp), pero sin descripción entera ni tags: no se leen ℗, links a Discogs ni créditos, y el cruce contra catálogo es más flojo.'

/** Cuántos candidatos devolver al pipeline. Enriquece 24; el resto es colchón
 *  para cuando "no me muestres lo que ya vi" descarta la mitad. */
const CANDIDATOS_POR_BUSQUEDA = 48

/** Convierte 'PT3M25S' a segundos. */
function parseISODuration(iso: string): number | undefined {
  const m = iso.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/)
  if (!m) return undefined
  const [, h, mm, s] = m
  return (Number(h ?? 0) * 3600) + (Number(mm ?? 0) * 60) + Number(s ?? 0)
}

/** El payload de `videos.list` que usamos (lo demás no se mira ni se persiste). */
interface VideoResource {
  id: string
  snippet?: {
    title?: string
    channelTitle?: string
    channelId?: string
    publishedAt?: string
    description?: string
    tags?: string[]
    thumbnails?: { medium?: { url?: string }; high?: { url?: string } }
  }
  contentDetails?: { duration?: string }
  statistics?: { viewCount?: string }
}

/** videos.list = 1 unidad y acepta hasta 50 ids por request. Barato: trae stats + duración. */
async function fetchStats(ids: string[]): Promise<Map<string, VideoResource>> {
  const out = new Map<string, VideoResource>()
  if (!KEY) return out
  for (let i = 0; i < ids.length; i += 50) {
    const params = new URLSearchParams({
      part: 'statistics,contentDetails,snippet',
      id: ids.slice(i, i + 50).join(','),
      key: KEY,
    })
    const res = await fetch(`${BASE}/videos?${params.toString()}`)
    if (!res.ok) throw new Error(`YouTube videos.list ${res.status}${res.status === 403 ? ' (¿quota agotada?)' : ''}`)
    const data = (await res.json()) as { items?: VideoResource[] }
    for (const it of data.items ?? []) out.set(it.id, it)
  }
  return out
}

/** SourceItem definitivo desde `videos.list`: views exactas, descripción, tags, fecha. */
function toItem(id: string, video: VideoResource): SourceItem {
  const sn = video.snippet ?? {}
  return {
    id: `youtube:${id}`,
    kind: 'youtube',
    nativeId: id,
    url: `https://www.youtube.com/watch?v=${id}`,
    title: sn.title ?? '',
    uploader: sn.channelTitle,
    channelId: sn.channelId,
    durationSec: video.contentDetails?.duration
      ? parseISODuration(video.contentDetails.duration)
      : undefined,
    views: video.statistics?.viewCount ? Number(video.statistics.viewCount) : undefined,
    viewsApprox: false,
    publishedAt: sn.publishedAt,
    thumbnail: sn.thumbnails?.medium?.url,
    description: sn.description,
    tags: sn.tags,
    raw: video,
  }
}

/**
 * SourceItem PROVISIONAL desde el listado flat de yt-dlp: alcanza para el
 * portero (basura dura), para "ya lo vi" y para mostrar la ficha; no alcanza
 * para los hints. `viewsApprox: true` para que nadie lo lea como exacto.
 */
function flatToItem(d: DiscoverItem, padre?: Pick<DiscoverListResult, 'uploader' | 'channel_id' | 'kind'>): SourceItem {
  // en un canal, el padre es el uploader de todo; en una playlist no (el dueño
  // de la playlist no es quien subió el video)
  const heredar = padre?.kind === 'channel'
  return {
    id: `youtube:${d.video_id}`,
    kind: 'youtube',
    nativeId: d.video_id,
    url: `https://www.youtube.com/watch?v=${d.video_id}`,
    title: d.title ?? '',
    uploader: d.uploader ?? (heredar ? padre?.uploader ?? undefined : undefined),
    channelId: d.channel_id ?? (heredar ? padre?.channel_id ?? undefined : undefined),
    durationSec: d.duration_sec ?? undefined,
    views: d.views ?? undefined,
    viewsApprox: d.views_approx ?? true,
    playlistIndex: d.playlist_index ?? undefined,
    thumbnail: d.thumbnail ?? undefined,
    description: d.description_snippet ?? undefined,
  }
}

/**
 * Basura dura sobre un item PROVISIONAL (flat / ytsearch / `search.list`), que
 * puede venir sin duración. `esBasura` trata 0 s como "vivo/estreno", y un
 * item sin duración es "no sé", no "en vivo": se evalúa solo el texto.
 */
export function esBasuraFlat(item: SourceItem): boolean {
  return esBasura(item.durationSec == null ? { ...item, durationSec: 240 } : item)
}

/**
 * Candidatos para una query, tal cual los devolvió la fuente (antes de
 * `videos.list`).
 *
 * Primero el backend con yt-dlp, que no gasta quota: con el fan-out de 3 lanes,
 * una búsqueda pasa de 303 unidades a 3 (solo los `videos.list`). Si el backend
 * no está levantado se cae a `search.list`, que anda por CORS desde el browser
 * pero cuesta 100 unidades por query. Sin backend y sin key no hay forma.
 */
async function buscarCandidatos(q: string): Promise<DiscoverItem[]> {
  try {
    return await discoverSearch(q, MAX_RESULTS_POR_BUSQUEDA)
  } catch (e) {
    if (!KEY) {
      const motivo = e instanceof Error ? e.message : String(e)
      throw new Error(`El backend no responde (${motivo}) y no hay VITE_YOUTUBE_API_KEY para buscar por la API.`)
    }
    return buscarConQuota(q)
  }
}

/** `search.list` (100 unidades): el snippet trae título, canal y un recorte de la descripción, sin views ni duración. */
async function buscarConQuota(q: string): Promise<DiscoverItem[]> {
  const params = new URLSearchParams({
    part: 'snippet',
    q,
    type: 'video',
    maxResults: String(MAX_RESULTS_POR_BUSQUEDA),
    key: KEY ?? '',
  })
  const res = await fetch(`${BASE}/search?${params.toString()}`)
  if (!res.ok) throw new Error(`YouTube search ${res.status}`)
  const data = (await res.json()) as {
    items?: Array<{ id?: { videoId?: string }; snippet?: VideoResource['snippet'] }>
  }
  const out: DiscoverItem[] = []
  for (const it of data.items ?? []) {
    const id = it.id?.videoId
    if (!id) continue
    const sn = it.snippet ?? {}
    out.push({
      video_id: id,
      title: sn.title ?? '',
      uploader: sn.channelTitle ?? null,
      channel_id: sn.channelId ?? null,
      thumbnail: sn.thumbnails?.medium?.url ?? null,
      description_snippet: sn.description ?? null,
    })
  }
  return out
}

export interface OpcionesDeBusqueda {
  /** cuántos candidatos devolver. Default 48. */
  limit?: number
  /** cuántas `search.list` gastar (100 unidades c/u). Default 3. */
  presupuesto?: number
  /** semilla de la rotación de sellos/artistas/años; por defecto rota por día */
  semilla?: number
  /** para medir: se llama con el plan y con lo que se descartó */
  onPlan?: (plan: PlanDeDigging) => void
  /** se llama si la búsqueda salió degradada (sin key o `videos.list` caído): qué se perdió */
  onAviso?: (aviso: string) => void
}

/**
 * Descubrimiento en YouTube: abanico de queries → dedupe → stats → anti-basura
 * → orden de digging.
 *
 * Con el backend levantado las búsquedas cuestan 0 y solo se paga `videos.list`
 * (1 unidad cada 50 ids). Sin backend, N `search.list` (100 unidades c/u): con
 * el presupuesto por defecto son **303 unidades**, ~33 búsquedas por día.
 *
 * Sin key, o con `videos.list` caído (quota agotada), NO se tira: se sigue con
 * lo que ya dio la búsqueda (yt-dlp trae views exactas, duración y un recorte
 * de la descripción) y se avisa por `onAviso`. Solo se tira cuando ninguna
 * lane pudo buscar (backend caído y sin key).
 */
export async function buscarEnYoutube(
  query: SearchQuery,
  opts: OpcionesDeBusqueda = {},
): Promise<SourceItem[]> {
  const plan = planificarQueries(query, {
    presupuesto: opts.presupuesto ?? PRESUPUESTO_POR_DEFECTO,
    semilla: opts.semilla,
  })
  opts.onPlan?.(plan)

  // En paralelo: una query que falle (quota, 400 por comillas raras) no puede
  // tumbar la búsqueda entera.
  const tandas = await Promise.allSettled(plan.queries.map((dq: DiggerQuery) => buscarCandidatos(dq.q)))

  // Si NINGUNA lane pudo buscar, el motivo es lo que importa (backend caído y
  // sin key): se tira con ese texto, no se devuelve una lista vacía muda.
  const fallida = tandas.find((r): r is PromiseRejectedResult => r.status === 'rejected')
  if (fallida && tandas.every((r) => r.status === 'rejected')) {
    throw fallida.reason instanceof Error ? fallida.reason : new Error(String(fallida.reason))
  }

  // Dedupe conservando la lane que lo encontró primero. Que un video aparezca
  // en varias lanes no lo hace mejor: suele ser el más obvio de la escena.
  const porId = new Map<string, { crudo: DiscoverItem; lane: CandidatoDeDigging['lane'] }>()
  for (const [i, r] of tandas.entries()) {
    if (r.status !== 'fulfilled') continue
    for (const crudo of r.value) {
      if (!porId.has(crudo.video_id)) porId.set(crudo.video_id, { crudo, lane: plan.queries[i].lane })
    }
  }
  if (!porId.size) return []

  // `videos.list`: views exactas, duración, descripción entera, tags. Sin key
  // o con la quota agotada se sigue con lo provisional, avisando qué se pierde.
  let stats = new Map<string, VideoResource>()
  let aviso: string | undefined
  if (!KEY) {
    aviso = AVISO_SIN_KEY
  } else {
    try {
      stats = await fetchStats([...porId.keys()])
    } catch (e) {
      aviso = `videos.list falló (${e instanceof Error ? e.message : String(e)}): esta búsqueda sale sin descripción entera ni tags (no se leen ℗ ni links a Discogs).`
    }
  }
  if (aviso) opts.onAviso?.(aviso)

  const candidatos: CandidatoDeDigging[] = []
  for (const [id, { crudo, lane }] of porId) {
    const video = stats.get(id)
    let item: SourceItem
    if (video) {
      item = toItem(id, video)
    } else if (aviso) {
      // degradado: lo que dio ytsearch (views exactas: el backend manda `views_approx: false`)
      item = flatToItem(crudo)
    } else {
      continue // con `videos.list` andando, lo que no devolvió está borrado o privado
    }
    if (esBasuraFlat(item)) continue
    candidatos.push({ item, lane })
  }

  // El vocabulario de la escena sirve dos veces: para armar las queries y para
  // reconocer, al volver, qué resultado es de la escena y cuál se coló.
  const escenas = ESCENAS.filter((e) => plan.escenas.includes(e.id))
  const ordenados = ordenarParaDigging(candidatos, {
    obvios: obviosDe(escenas),
    anio: plan.anio,
    origen: 'busqueda',
    pertinentes: escenas.flatMap((e) => [
      ...e.gatillos,
      ...e.populares,
      ...e.jerga,
      ...e.sellos,
      ...e.artistas,
      ...(e.nativo?.terminos ?? []),
    ]),
  })
  return ordenados.slice(0, opts.limit ?? CANDIDATOS_POR_BUSQUEDA)
}

export const youtube: DiscoverySource = {
  kind: 'youtube',
  search: (query, opts) => buscarEnYoutube(query, { limit: opts?.limit, onAviso: opts?.onAviso }),
}

// ---------- referencias: qué pegó el usuario ----------

/**
 * Saca el playlistId de una URL de YouTube, o devuelve la entrada si ya es un ID.
 * Acepta `?list=`, la forma /playlist?list= y el ID pelado.
 */
export function parsePlaylistId(input: string): string | null {
  const trimmed = input.trim()
  if (!trimmed) return null

  const fromUrl = trimmed.match(/[?&]list=([A-Za-z0-9_-]+)/)
  if (fromUrl) return fromUrl[1]

  // un ID suelto: prefijos conocidos (PL/UU/LL/FL/OL) o el mix de "watch later"
  return /^[A-Za-z0-9_-]{12,}$/.test(trimmed) ? trimmed : null
}

/** Una veta que el usuario pegó o eligió: playlist ajena o canal entero. */
export interface VetaRef {
  kind: 'playlist' | 'channel'
  /** lo que se le pasa al backend: id (PL…/UC…), @handle o URL */
  ref: string
  /** nombre para mostrar mientras el backend no devolvió el título real */
  nombre?: string
}

/**
 * Interpreta lo que pegó el usuario: una URL de playlist, de canal, un id o
 * un @handle. Devuelve null si no parece nada de eso. La validación fina la
 * hace el backend (400 con detail si no es una referencia de YouTube).
 */
export function parseVetaRef(input: string): VetaRef | null {
  const s = input.trim()
  if (!s) return null
  // playlist: ?list= o id PL…/UU…/OL…/FL…/LL…
  const list = s.match(/[?&]list=([A-Za-z0-9_-]+)/)?.[1]
  if (list) {
    // los mixes RD… no se listan (el backend los rechaza): no vale la pena mandarlos
    if (/^RD/.test(list)) return null
    return { kind: 'playlist', ref: list }
  }
  if (/^UC[A-Za-z0-9_-]{22}$/.test(s)) return { kind: 'channel', ref: s }
  if (/^(PL|UU|OL|FL|LL)[A-Za-z0-9_-]{10,}$/.test(s)) return { kind: 'playlist', ref: s }
  if (/^@[A-Za-z0-9._-]{3,}$/.test(s)) return { kind: 'channel', ref: s, nombre: s }
  if (/youtu\.?be/.test(s)) {
    // URL de canal: /channel/UC…, /@handle, /c/…, /user/… (con o sin /videos)
    if (/\/(channel\/UC[A-Za-z0-9_-]{22}|@[A-Za-z0-9._-]+|c\/[^/?#]+|user\/[^/?#]+)/.test(s)) {
      const handle = s.match(/\/(@[A-Za-z0-9._-]+)/)?.[1]
      return { kind: 'channel', ref: s, nombre: handle }
    }
    return null
  }
  // un handle sin arroba ("oleg_samples"): el backend lo resuelve
  if (/^[A-Za-z0-9._-]{3,30}$/.test(s) && !/^[0-9]+$/.test(s)) return { kind: 'channel', ref: s, nombre: `@${s}` }
  return null
}

// ---------- import de playlists propias ----------

export interface PlaylistFetch {
  /** título tal cual está en YouTube; se usa como tag */
  title: string
  items: SourceItem[]
}

/** "JAPANESE CITY POP SAMPLES" → "japanese city pop". El sufijo no aporta nada. */
export function playlistTag(title: string): string {
  const stripped = title.replace(/\bsamples?\b/gi, '').replace(/\s{2,}/g, ' ').trim()
  return (stripped || title).toLowerCase()
}

/**
 * Trae todos los videos de una playlist como SourceItems, más su título.
 *
 * Primero el backend (yt-dlp flat, 0 quota) para listar y `videos.list` para
 * la metadata rica (1 unidad cada 50). Si el backend no está, `playlistItems`
 * de la API (también 1 unidad cada 50). Sin key y sin backend no hay forma.
 */
export async function fetchPlaylist(playlistId: string): Promise<PlaylistFetch> {
  let title = playlistId
  let ids: string[] = []
  let flat: SourceItem[] = []
  try {
    const tanda = await listarVeta({ kind: 'playlist', ref: playlistId }, 0, 500)
    title = tanda.nombre
    flat = tanda.items
    let next = tanda.nextOffset
    while (next != null) {
      const mas = await listarVeta({ kind: 'playlist', ref: playlistId }, next, 500)
      flat.push(...mas.items)
      next = mas.nextOffset
    }
    ids = flat.map((i) => i.nativeId)
  } catch (e) {
    if (e instanceof BackendError && e.reachable) throw e // 404 privada, 400 ref inválida: no hay fallback que valga
    if (!KEY) throw new Error('Ni el backend ni VITE_YOUTUBE_API_KEY están disponibles para leer la playlist.')
    const porApi = await fetchPlaylistConQuota(playlistId)
    title = porApi.title
    ids = porApi.ids
  }

  if (!KEY) {
    // sin key: lo que dio el flat, y que el cruce haga lo que pueda
    return { title, items: flat }
  }
  const stats = await fetchStats(ids)
  // los borrados/privados quedan sin stats: no sirven como entidad
  const items = ids.filter((id) => stats.has(id)).map((id) => toItem(id, stats.get(id) as VideoResource))
  return { title, items }
}

async function fetchPlaylistConQuota(playlistId: string): Promise<{ title: string; ids: string[] }> {
  const metaRes = await fetch(`${BASE}/playlists?part=snippet&id=${playlistId}&key=${KEY}`)
  if (!metaRes.ok) throw new Error(`YouTube playlists ${metaRes.status}`)
  const meta = (await metaRes.json()) as { items?: Array<{ snippet?: { title?: string } }> }
  const title: string = meta.items?.[0]?.snippet?.title ?? playlistId

  const ids: string[] = []
  let pageToken: string | undefined
  do {
    const params = new URLSearchParams({
      part: 'contentDetails',
      playlistId,
      maxResults: '50',
      key: KEY ?? '',
    })
    if (pageToken) params.set('pageToken', pageToken)
    const res = await fetch(`${BASE}/playlistItems?${params.toString()}`)
    if (!res.ok) {
      const detail = res.status === 404 ? ' (¿la playlist es privada?)' : ''
      throw new Error(`YouTube playlistItems ${res.status}${detail}`)
    }
    const data = (await res.json()) as {
      items?: Array<{ contentDetails?: { videoId?: string } }>
      nextPageToken?: string
    }
    for (const it of data.items ?? []) {
      const id = it.contentDetails?.videoId
      if (id) ids.push(id)
    }
    pageToken = data.nextPageToken
  } while (pageToken)
  return { title, ids }
}

// ---------- vetas: playlists y canales de otros diggers ----------

/** Una tanda del listado plano de una veta, ya sin borrados. */
export interface TandaDeVeta {
  kind: 'playlist' | 'channel'
  /** id canónico que devolvió el backend (PL… / UC…) */
  id: string
  nombre: string
  uploader?: string
  channelId?: string
  url?: string
  /** cuántos hay en total; undefined si YouTube no lo dice (tab de canal sin UU) */
  total?: number
  offset: number
  /** cursor para la próxima tanda; undefined cuando se terminó */
  nextOffset?: number
  /** items usables (sin `[Deleted video]`), provisionales: sin descripción ni tags */
  items: SourceItem[]
  /** cuántos venían borrados/privados en esta tanda */
  noDisponibles: number
}

/**
 * Lista una tanda de una veta con yt-dlp (0 quota, sin key). Descarta lo no
 * disponible; NO descarta basura ni rankea (eso es del pipeline). `offset` es
 * el cursor del backend, `nextOffset` el siguiente (undefined al final).
 */
export async function listarVeta(
  veta: VetaRef,
  offset = 0,
  limit = DISCOVER_LIST_DEFAULT,
): Promise<TandaDeVeta> {
  const res =
    veta.kind === 'playlist'
      ? await discoverPlaylist(veta.ref, offset, limit)
      : await discoverChannel(veta.ref, offset, limit)
  const noDisponibles = res.items.filter((d) => d.unavailable).length
  const items = res.items.filter((d) => !d.unavailable && d.video_id).map((d) => flatToItem(d, res))
  return {
    kind: res.kind,
    id: res.id,
    nombre: res.title || veta.nombre || veta.ref,
    uploader: res.uploader ?? undefined,
    channelId: res.channel_id ?? undefined,
    url: res.url ?? undefined,
    total: res.total ?? undefined,
    offset: res.offset,
    nextOffset: res.next_offset ?? undefined,
    items,
    noDisponibles,
  }
}

/**
 * Completa una tanda provisional (flat) con `videos.list`: descripción, tags,
 * fecha, views exactas y duración. Es el ÚNICO gasto de quota de una veta y se
 * hace solo sobre lo que se va a enriquecer (1 unidad cada 50 ids).
 *
 * Sin key devuelve los mismos items y `aviso`: se cava igual, con hints pobres.
 * Lo que `videos.list` no devuelve (borrado entre el listado y ahora) se cae.
 */
export async function enriquecerTanda(
  items: SourceItem[],
): Promise<{ items: SourceItem[]; aviso?: string }> {
  if (!KEY) return { items, aviso: AVISO_SIN_KEY }
  const ids = items.filter((i) => i.kind === 'youtube').map((i) => i.nativeId)
  let stats: Map<string, VideoResource>
  try {
    stats = await fetchStats(ids)
  } catch (e) {
    // quota agotada o red: seguir con lo provisional, avisando
    return {
      items,
      aviso: `videos.list falló (${e instanceof Error ? e.message : String(e)}): esta tanda se cava sin descripción ni tags.`,
    }
  }
  const out: SourceItem[] = []
  for (const it of items) {
    if (it.kind !== 'youtube') {
      out.push(it)
      continue
    }
    const video = stats.get(it.nativeId)
    if (!video) continue // borrado desde que se listó
    const rico = toItem(it.nativeId, video)
    // lo que el flat sabía y `videos.list` no: la posición en la veta
    out.push({ ...rico, playlistIndex: it.playlistIndex })
  }
  return { items: out }
}

// ---------- minería de canales (camino viejo, por la API) ----------

/**
 * Los uploads de un canal por la API oficial (playlist `UU…`, 1 unidad cada 50).
 * Es el respaldo cuando el backend no está: las vetas normales van por
 * `listarVeta` (yt-dlp, 0 quota, sin tope de 100 y con el total del canal).
 */
export async function fetchChannelUploads(channelId: string, max = 100): Promise<SourceItem[]> {
  if (!KEY) throw new Error('Falta VITE_YOUTUBE_API_KEY')
  if (!channelId.startsWith('UC')) throw new Error(`channelId inesperado: ${channelId}`)

  const uploads = `UU${channelId.slice(2)}`
  const ids: string[] = []
  let pageToken: string | undefined

  do {
    const params = new URLSearchParams({
      part: 'contentDetails',
      playlistId: uploads,
      maxResults: '50',
      key: KEY,
    })
    if (pageToken) params.set('pageToken', pageToken)
    const res = await fetch(`${BASE}/playlistItems?${params.toString()}`)
    if (!res.ok) throw new Error(`YouTube uploads ${res.status}`)
    const data = (await res.json()) as {
      items?: Array<{ contentDetails?: { videoId?: string } }>
      nextPageToken?: string
    }
    for (const it of data.items ?? []) {
      const id = it.contentDetails?.videoId
      if (id) ids.push(id)
    }
    pageToken = data.nextPageToken
  } while (pageToken && ids.length < max)

  const stats = await fetchStats(ids.slice(0, max))
  return ids
    .slice(0, max)
    .filter((id) => stats.has(id))
    .map((id) => toItem(id, stats.get(id) as VideoResource))
}
