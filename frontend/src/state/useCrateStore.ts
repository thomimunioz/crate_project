/**
 * Store principal (Zustand): query, resultados, affinity y acciones.
 * Ata el pipeline (Capa 1) con el crate-index (Dexie) y el backend (Capa 2).
 */
import { create } from 'zustand'
import type { EnrichedTrack, SearchQuery } from '@/core/entities'
import type { Affinity } from '@/core/affinity'
import { emptyAffinity } from '@/core/affinity'
import {
  runSearch,
  importPlaylist,
  identifyByFingerprint,
  abrirVeta,
  listarMas,
  proximaTanda,
  cavarVeta,
  ENRICH_LIMIT,
  type EstadoDeVeta,
} from '@/pipeline'
import { parsePlaylistId, type VetaRef } from '@/sources/youtube'
import * as crate from '@/db/crateIndex'
import type { HitRate, TrackAnalysis } from '@/db/crateIndex'
import { purgeExpired } from '@/db/cache'
import { analyzeAudio, health, BackendError, type Health } from '@/api/backend'

export type View = 'search' | 'crate'

/** Lo que la UI muestra de la veta que se está cavando. */
export interface Mining {
  kind: 'playlist' | 'channel'
  /** id canónico (PL… / UC…) o, hasta que el backend responda, lo que se pegó */
  id: string
  nombre: string
  /** cuántos de la veta ya pasaron por tus ojos: cavados ahora + saltados por "ya lo vi" */
  visto: number
  /** cuántos tiene la veta (si YouTube no lo dice, cuántos se listaron) */
  total: number
  /** cuántos quedan por cavar (pool + lo que falta listar) */
  quedan: number
  /** descartados sin cavar: borrados, basura dura, repetidos */
  descartados: number
  /** no queda nada por cavar */
  agotada: boolean
  /** se está cavando sin API key o `videos.list` falló: hints pobres */
  aviso?: string
}

interface CrateState {
  view: View
  query: SearchQuery
  results: EnrichedTrack[]
  /** el crate real: saved + analyzed. Se carga on demand. */
  crateTracks: EnrichedTrack[]
  loading: boolean
  analyzing: string | null
  /** crateId del track que se está identificando por huella */
  identifying: string | null
  /** progreso del cruce contra catálogo durante una búsqueda o una tanda */
  enriching: { done: number; total: number } | null
  /** la veta que se está cavando, si la vista viene de una playlist/canal */
  mining: Mining | null
  /** progreso del import; null si no hay uno corriendo */
  importing: { label: string; done: number; total: number } | null
  error?: string
  /** la última búsqueda salió degradada (sin key, quota agotada, una fuente caída): qué se perdió */
  aviso?: string
  affinity: Affinity
  hideSeen: boolean
  ready: boolean
  /** estado del backend (`/health`); null = todavía no se preguntó o no responde */
  backend: Health | null
  backendChecked: boolean
  /** evidencia del análisis de audio por crateId (BPM crudo, alternativas, ventana) */
  analyses: Record<string, TrackAnalysis | undefined>
  /** hit rate por búsqueda/veta: la métrica del producto, medida sobre uso real */
  hitRates: Array<HitRate & { queryText: string }>

  init: () => Promise<void>
  checkBackend: (refresh?: boolean) => Promise<void>
  setView: (v: View) => Promise<void>
  patchQuery: (q: Partial<SearchQuery>) => void
  search: () => Promise<void>
  /** cava una playlist o un canal ajeno: primera tanda */
  mine: (veta: VetaRef) => Promise<void>
  /** siguiente tanda de la veta abierta */
  mineMore: () => Promise<void>
  loadCrate: () => Promise<void>
  importPlaylists: (input: string) => Promise<void>
  /** guardar, opcionalmente en una colección (tag) tuya */
  save: (t: EnrichedTrack, tags?: string[]) => Promise<void>
  remove: (t: EnrichedTrack) => Promise<void>
  /** "no me interesa": rechazado, resta affinity, no se muestra más */
  reject: (t: EnrichedTrack) => Promise<void>
  /** "no para esta búsqueda": se oculta acá y nada más; no dice nada del disco */
  skip: (t: EnrichedTrack) => Promise<void>
  analyze: (t: EnrichedTrack) => Promise<void>
  identify: (t: EnrichedTrack) => Promise<void>
  /** corrección de la octava a mano (÷2 / ×2): provenance user/manual */
  setBpm: (t: EnrichedTrack, value: number) => Promise<void>
  loadAnalysis: (crateId: string) => Promise<void>
  toggleHideSeen: () => void
}

/** La veta abierta vive fuera del estado renderizado: el pool puede ser de miles. */
let vetaActual: EstadoDeVeta | null = null
/** id de la sesión de digging en curso (una por búsqueda o veta), para el hit rate */
let sessionId = ''

const nuevaSesion = (): string => {
  sessionId = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`
  return sessionId
}

/** Cómo se lee un error para el usuario. Los del backend traen su `detail`. */
function mensajeDe(e: unknown): string {
  if (e instanceof BackendError) {
    switch (e.kind) {
      case 'unreachable':
        return 'El backend no responde. Levantalo con `uvicorn app.main:app --port 8787` (ver README).'
      case 'toolchain':
        return `El backend no puede bajar audio: ${e.detail}`
      case 'unavailable':
        return e.detail
      case 'bad_request':
        return e.detail
      default:
        return `Falló el backend (${e.status}): ${e.detail}`
    }
  }
  return e instanceof Error ? e.message : String(e)
}

/**
 * Dónde arranca la ventana de análisis: 60 s si el track dura más de 150 s, si
 * no el 20% de la duración. Nunca la intro. Es la misma regla que aplica el
 * backend cuando no se manda nada; se manda igual para que la ficha diga
 * exactamente qué se analizó aunque el backend cambie el default.
 */
export function ventanaDeAnalisis(durationSec?: number): number | undefined {
  if (!durationSec || durationSec <= 0) return undefined
  return durationSec > 150 ? 60 : Math.round(durationSec * 0.2)
}

/**
 * Ids de fuente que descartaste "no para esta búsqueda" (`skipFor`) en este
 * contexto. Se aplica SIEMPRE, con «ocultando vistos» prendido o no: es una
 * decisión tuya sobre este contexto, no un filtro de historial. (Con hideSeen
 * prendido `knownSourceIds` ya los incluye, así que ahí no hace falta leerlo.)
 * Hasta que crateIndex lo exponga (`skippedSourceIdsFor`, con índice), se lee acá.
 */
async function descartadosPara(contexto: string): Promise<Set<string>> {
  const out = new Set<string>()
  if (!contexto) return out
  await crate.db.tracks
    .filter((t) => t.skippedFor?.includes(contexto) ?? false)
    .each((t) => t.sourceIds.forEach((id) => out.add(id)))
  return out
}

/** Qué no enriquecer en este contexto: todo lo visto (si se oculta) o, si no, solo lo que descartaste acá. */
async function idsASaltar(hideSeen: boolean, contexto: string): Promise<Set<string>> {
  return hideSeen ? crate.knownSourceIds() : descartadosPara(contexto)
}

function resumenDeVeta(estado: EstadoDeVeta, cavados: number, saltados: number, aviso?: string): Mining {
  const listadoEntero = estado.nextOffset == null
  const pendientesDeListar = !listadoEntero && estado.total != null
    ? Math.max(0, estado.total - estado.listados)
    : 0
  const quedan = estado.pool.length + pendientesDeListar
  return {
    kind: estado.veta.kind,
    id: estado.id ?? estado.veta.ref,
    nombre: estado.nombre,
    visto: cavados + saltados,
    // el total que declara YouTube puede no coincidir con lo que devuelve el
    // listado; una vez listada entera, lo que se listó ES el total
    total: listadoEntero ? estado.listados : (estado.total ?? estado.listados),
    quedan,
    descartados: estado.descartados,
    agotada: quedan === 0 && estado.nextOffset == null,
    aviso,
  }
}

export const useCrate = create<CrateState>((set, get) => ({
  view: 'search',
  query: { text: '' },
  results: [],
  crateTracks: [],
  loading: false,
  analyzing: null,
  identifying: null,
  enriching: null,
  mining: null,
  importing: null,
  affinity: emptyAffinity(),
  hideSeen: true,
  ready: false,
  backend: null,
  backendChecked: false,
  analyses: {},
  hitRates: [],

  async init() {
    void purgeExpired() // en background: no vale la pena bloquear el arranque
    void get().checkBackend()
    const affinity = await crate.getAffinity()
    set({ affinity, ready: true })
    await get().loadCrate()
  },

  /** Pregunta al backend qué herramientas tiene. No bloquea nada: solo informa a la UI. */
  async checkBackend(refresh = false) {
    try {
      const h = await health({ refresh })
      set({ backend: h, backendChecked: true })
    } catch {
      set({ backend: null, backendChecked: true })
    }
  },

  async setView(view) {
    set({ view })
    if (view === 'crate') await get().loadCrate()
  },

  patchQuery(q) {
    set({ query: { ...get().query, ...q } })
  },

  /** Acepta varias playlists, una URL por línea. */
  async importPlaylists(input) {
    const ids = input
      .split(/[\n,]/)
      .map((line) => parsePlaylistId(line))
      .filter((id): id is string => Boolean(id))

    if (ids.length === 0) {
      set({ error: 'No pude leer ninguna playlist. Pegá las URLs completas, una por línea.' })
      return
    }

    set({ importing: { label: 'leyendo…', done: 0, total: 0 }, error: undefined })
    const failed: string[] = []
    try {
      for (const [i, id] of ids.entries()) {
        const pos = ids.length > 1 ? ` (${i + 1}/${ids.length})` : ''
        try {
          const { tag, tracks } = await importPlaylist(id, (done, total) =>
            set({ importing: { label: `${get().importing?.label ?? ''}`, done, total } }),
          )
          set({ importing: { label: tag + pos, done: 0, total: tracks.length } })
          for (const track of tracks) await crate.saveFromPlaylist(track, tag)
        } catch (e) {
          failed.push(`${id}: ${mensajeDe(e)}`)
        }
      }
      set({ affinity: await crate.getAffinity() })
      await get().loadCrate()
      if (failed.length) set({ error: `No se pudieron importar: ${failed.join(' · ')}` })
    } finally {
      set({ importing: null })
    }
  },

  async loadCrate() {
    const [crateTracks, hitRates] = await Promise.all([crate.getCrate(), crate.hitRatePorQuery()])
    crateTracks.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
    set({ crateTracks, hitRates })
  },

  async search() {
    const { query, affinity, hideSeen } = get()
    if (!query.text.trim()) return
    vetaActual = null
    const sesion = nuevaSesion()
    set({ mining: null, loading: true, error: undefined, aviso: undefined, results: [], enriching: null })
    try {
      // descartar lo ya visto (o lo que dijiste "no para esta búsqueda") ANTES
      // de enriquecer: no se gasta red en tirarlo después
      const skipSourceIds = await idsASaltar(hideSeen, query.text.trim())
      const results = await runSearch(query, affinity, {
        skipSourceIds,
        onAviso: (aviso) => set({ aviso }),
        onPartial: (parciales) =>
          set({
            results: parciales,
            enriching: { done: parciales.filter((t) => !t.pending).length, total: parciales.length },
          }),
      })
      const shownAt = new Date().toISOString()
      await Promise.all(
        results.map((t) =>
          crate.markSeen(t, { queryText: query.text, shownAt, origen: 'busqueda', sessionId: sesion }),
        ),
      )
      set({ results })
    } catch (e) {
      set({ error: mensajeDe(e) })
    } finally {
      set({ loading: false, enriching: null })
    }
  },

  /**
   * Abre una veta (playlist o canal ajeno) y cava la primera tanda. Los temas
   * entran como `seen` con contexto, NUNCA como saved: la veta es de otro.
   */
  async mine(veta) {
    nuevaSesion()
    set({
      view: 'search',
      loading: true,
      error: undefined,
      aviso: undefined,
      results: [],
      enriching: null,
      mining: {
        kind: veta.kind,
        id: veta.ref,
        nombre: veta.nombre ?? veta.ref,
        visto: 0,
        total: 0,
        quedan: 0,
        descartados: 0,
        agotada: false,
      },
    })
    try {
      vetaActual = await abrirVeta(veta)
      set({ mining: resumenDeVeta(vetaActual, 0, 0) })
    } catch (e) {
      vetaActual = null
      set({ error: mensajeDe(e), loading: false, mining: null })
      return
    }
    await get().mineMore()
  },

  /** La próxima tanda de la veta abierta. Lo ya visto se salta y cuenta como visto. */
  async mineMore() {
    const estado = vetaActual
    const { query, affinity, hideSeen, mining } = get()
    if (!estado || !mining || mining.agotada) return
    set({ loading: true, error: undefined, enriching: null })
    const sesion = sessionId || nuevaSesion()
    const previos = get().results
    try {
      const skipSourceIds = await idsASaltar(hideSeen, `veta:${estado.nombre}`)
      const pendientes = (s: EstadoDeVeta): number =>
        s.pool.filter((i) => !skipSourceIds.has(i.id)).length

      // listar hasta tener una tanda de no vistos (o hasta que la veta se acabe)
      let actual = estado
      while (pendientes(actual) < ENRICH_LIMIT && actual.nextOffset != null) {
        actual = await listarMas(actual)
        vetaActual = actual
        set({ mining: resumenDeVeta(actual, mining.visto, 0, mining.aviso) })
      }

      const { tanda, estado: siguiente, saltados } = proximaTanda(actual, query, affinity, skipSourceIds)
      vetaActual = siguiente
      const vistoBase = mining.visto + saltados
      if (tanda.length === 0) {
        set({ mining: { ...resumenDeVeta(siguiente, vistoBase, 0, mining.aviso), agotada: true } })
        return
      }
      set({ mining: resumenDeVeta(siguiente, vistoBase, 0, mining.aviso) })

      const { tracks, aviso } = await cavarVeta(tanda, query, affinity, {
        skipSourceIds,
        onPartial: (parciales) =>
          set({
            results: [...previos, ...parciales],
            enriching: { done: parciales.filter((t) => !t.pending).length, total: parciales.length },
          }),
      })
      const shownAt = new Date().toISOString()
      // el hit rate de una veta se mide por la veta: la query es solo el lente
      const queryText = `veta:${siguiente.nombre}`
      await Promise.all(
        tracks.map((t) => crate.markSeen(t, { queryText, shownAt, origen: 'veta', sessionId: sesion })),
      )
      // lo que `videos.list` ya no devolvió (borrado entre listar y cavar) no
      // pasó por tus ojos ni queda por cavar: cuenta como descartado, si no la
      // veta agotada nunca llega al total
      const caidos = Math.max(0, tanda.length - tracks.length)
      vetaActual = { ...siguiente, descartados: siguiente.descartados + caidos }
      set({
        results: [...previos, ...tracks],
        mining: resumenDeVeta(vetaActual, vistoBase + tracks.length, 0, aviso ?? mining.aviso),
      })
    } catch (e) {
      set({ error: mensajeDe(e) })
    } finally {
      set({ loading: false, enriching: null })
    }
  },

  async save(t, tags) {
    const affinity = await crate.save(t, { tags })
    const saved: EnrichedTrack = {
      ...t,
      status: t.status === 'analyzed' ? 'analyzed' : 'saved',
      tags: Array.from(new Set([...(t.tags ?? []), ...(tags ?? [])])),
    }
    set({
      affinity,
      results: get().results.map((r) => (r.crateId === t.crateId ? saved : r)),
      crateTracks: [saved, ...get().crateTracks.filter((r) => r.crateId !== t.crateId)],
    })
  },

  async remove(t) {
    const affinity = await crate.remove(t)
    set({
      affinity,
      results: get().results.map((r) =>
        r.crateId === t.crateId ? { ...r, status: 'seen' } : r,
      ),
      crateTracks: get().crateTracks.filter((r) => r.crateId !== t.crateId),
    })
  },

  async reject(t) {
    const affinity = await crate.reject(t)
    set({
      affinity,
      results: get().results.filter((r) => r.crateId !== t.crateId),
      crateTracks: get().crateTracks.filter((r) => r.crateId !== t.crateId),
    })
  },

  /**
   * "No para esta búsqueda": Thomas redistribuye entre listas, y un "no encaja
   * en 80s" no dice nada del disco. Se oculta en este contexto sin restar
   * affinity; en otra búsqueda puede volver a aparecer.
   */
  async skip(t) {
    const { query, mining } = get()
    const contexto = mining ? `veta:${mining.nombre}` : query.text.trim()
    await crate.skipFor(t, contexto)
    set({ results: get().results.filter((r) => r.crateId !== t.crateId) })
  },

  /**
   * Identifica por huella acústica: el desempate cuando el título no se puede
   * leer. La huella cambia el crateId (`guess:…` → `mb:…`), así que la fila
   * vieja migra a la nueva: hereda el contexto en que se mostró (hit rate),
   * los "no para esta búsqueda", la colección y el lugar en el crate; y la
   * affinity desaprende la identidad vieja y aprende la confirmada (artista,
   * año, géneros). Hasta que crateIndex exponga `reidentify(oldId, track)`,
   * se compone acá con lo que hay.
   */
  async identify(t) {
    set({ identifying: t.crateId, error: undefined })
    try {
      const { query, affinity } = get()
      const identificado = await identifyByFingerprint(t, query, affinity)
      const vieja = identificado.crateId !== t.crateId ? await crate.db.tracks.get(t.crateId) : undefined
      if (!vieja) {
        await crate.markSeen(identificado)
      } else {
        await crate.markSeen(identificado, vieja.shown)
        for (const contexto of vieja.skippedFor ?? []) await crate.skipFor(identificado, contexto)
        if (vieja.status === 'saved' || vieja.status === 'analyzed') {
          // -1 con la fila tal cual se aprendió al guardar, +1 con lo confirmado
          await crate.remove(vieja)
          await crate.save(identificado, { tags: vieja.tags })
          if (vieja.status === 'analyzed') await crate.db.tracks.update(identificado.crateId, { status: 'analyzed' })
        }
        const analisis = await crate.getAnalysis(t.crateId)
        if (analisis) {
          await crate.db.analyses.put({ ...analisis, crateId: identificado.crateId })
          await crate.db.analyses.delete(t.crateId)
        }
        // la fila vieja era la misma fuente con una identidad provisoria: ya no representa nada
        await crate.db.tracks.delete(t.crateId)
      }
      const reemplazar = (lista: EnrichedTrack[]): EnrichedTrack[] =>
        lista.map((r) => (r.sources[0]?.id === t.sources[0]?.id ? identificado : r))
      const { [t.crateId]: analisisViejo, ...otrosAnalisis } = get().analyses
      set({
        results: reemplazar(get().results),
        crateTracks: reemplazar(get().crateTracks),
        analyses: analisisViejo
          ? { ...otrosAnalisis, [identificado.crateId]: { ...analisisViejo, crateId: identificado.crateId } }
          : get().analyses,
        affinity: vieja ? await crate.getAffinity() : get().affinity,
      })
    } catch (e) {
      set({ error: mensajeDe(e) })
    } finally {
      set({ identifying: null })
    }
  },

  async analyze(t) {
    const src = t.sources[0]
    if (!src) return
    set({ analyzing: t.crateId, error: undefined })
    try {
      const result = await analyzeAudio(src.url, { startSec: ventanaDeAnalisis(src.durationSec) })
      const merged = await crate.saveAnalysis(t, result)
      const analysis = await crate.getAnalysis(t.crateId)
      set({
        results: get().results.map((r) => (r.crateId === t.crateId ? merged : r)),
        crateTracks: get().crateTracks.map((r) => (r.crateId === t.crateId ? merged : r)),
        analyses: { ...get().analyses, [t.crateId]: analysis },
        affinity: await crate.getAffinity(),
      })
      // el 503 se ve una vez; si el usuario instaló algo, que /health lo refleje
      if (!get().backend?.ok) void get().checkBackend(true)
    } catch (e) {
      set({ error: mensajeDe(e) })
      if (e instanceof BackendError && (e.kind === 'toolchain' || e.kind === 'unreachable')) {
        void get().checkBackend(true)
      }
    } finally {
      set({ analyzing: null })
    }
  },

  async setBpm(t, value) {
    if (!(value > 0)) return
    const merged = await crate.setBpmManual(t, value)
    const analysis = await crate.getAnalysis(t.crateId)
    set({
      results: get().results.map((r) => (r.crateId === t.crateId ? { ...r, bpm: merged.bpm } : r)),
      crateTracks: get().crateTracks.map((r) => (r.crateId === t.crateId ? { ...r, bpm: merged.bpm } : r)),
      analyses: { ...get().analyses, [t.crateId]: analysis },
      // la corrección a mano es el dato que DEBERÍA recalibrar el prior de
      // tempo, pero hoy `setBpmManual` no toca la affinity (queda para
      // crateIndex: restar el bucket viejo y sumar el corregido). Se recarga
      // igual para que la UI refleje lo que haya.
      affinity: await crate.getAffinity(),
    })
  },

  async loadAnalysis(crateId) {
    if (crateId in get().analyses) return
    const analysis = await crate.getAnalysis(crateId)
    set({ analyses: { ...get().analyses, [crateId]: analysis } })
  },

  toggleHideSeen() {
    set({ hideSeen: !get().hideSeen })
  },
}))
