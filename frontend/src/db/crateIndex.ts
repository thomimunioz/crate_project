/**
 * Crate-index local en IndexedDB (Dexie). Estados: seen / saved / analyzed / rejected.
 * El crate real = saved + analyzed. `seen` habilita "no me muestres lo que ya vi"
 * y, desde v3, guarda el contexto en que se mostró cada ficha para que la app
 * pueda medir su propio hit rate (mostradas / guardadas por búsqueda o sesión).
 * Ver docs/ENTITY_MODEL.md
 */
import Dexie, { type Table } from 'dexie'
import type { EnrichedTrack, SourceItem } from '@/core/entities'
import type { Affinity } from '@/core/affinity'
import { emptyAffinity, learn, learnBpmOnly, tasteTempoRange } from '@/core/affinity'
import type { AnalyzeResult } from '@/api/backend'
import type { CacheRow } from './cache'
import { analyzed, prov, type Provenanced } from '@/core/provenance'
import { foldBpm, type BpmAlternative, type TempoRange } from '@/core/tempo'

/** Dónde y cuándo se mostró una ficha: lo que hace falta para el hit rate. */
export interface ShownContext {
  queryText: string
  shownAt: string
  origen?: 'veta' | 'busqueda'
  /** id de la sesión de digging (una por búsqueda/veta corrida); lo pone el store */
  sessionId?: string
}

/**
 * La fila persistida: la ficha más lo que necesitan los índices y la métrica.
 * `sourceIds` está denormalizado para el índice multiEntry (hideSeen sin leer
 * la tabla entera); `shown` es el contexto de la última vez que se mostró.
 */
export interface CrateRow extends EnrichedTrack {
  sourceIds: string[]
  shown?: ShownContext
  /** "no para esta búsqueda": se oculta en ese contexto sin restar affinity */
  skippedFor?: string[]
  /**
   * Cuándo entró al crate (save / import / análisis). El hit rate cuenta como
   * acierto solo lo guardado DESPUÉS de mostrado: una ficha importada de
   * playlist que reaparece en una búsqueda no es un hallazgo de esa búsqueda.
   */
  savedAt?: string
}

/**
 * Evidencia del análisis de audio, aparte de la ficha: el BPM crudo con sus
 * alternativas y la ventana analizada. La ficha lleva el valor elegido con su
 * provenance (analizado o inferido); acá queda lo que permitió elegirlo, para
 * que el AnalyzePanel lo muestre y el usuario lo corrija (÷2 / ×2).
 */
export interface TrackAnalysis {
  crateId: string
  bpmRaw?: Provenanced<number>
  alternatives?: BpmAlternative[]
  ambiguous?: boolean
  window?: { start_sec: number; seconds: number }
  /** true si el valor de la ficha es otra octava que la que trajo el DSP */
  folded: boolean
  /** el rango que se usó para plegar, como estaba en ese momento */
  prior?: TempoRange
  reason?: string
  updatedAt: string
}

/** Lo que trae `POST /analyze` para el BPM, con la evidencia de C2 si el backend ya la manda. */
interface BpmResultConEvidencia {
  value: number
  confidence: number
  alternatives?: BpmAlternative[]
  ambiguous?: boolean
  window?: { start_sec: number; seconds: number }
}

class CrateDB extends Dexie {
  tracks!: Table<CrateRow, string>
  meta!: Table<{ key: string; value: unknown }, string>
  cache!: Table<CacheRow, string>
  analyses!: Table<TrackAnalysis, string>

  constructor() {
    super('crate')
    this.version(1).stores({
      // índices: pk crateId, filtrables status/year/updatedAt, multiEntry en géneros
      tracks: 'crateId, status, entity.year, updatedAt, *entity.genres',
      meta: 'key',
    })
    // v2: cache de catálogo (Discogs/MusicBrainz). Ver db/cache.ts
    this.version(2).stores({ cache: 'key, expiresAt' })
    // v3: índices multiEntry por id de fuente y por colección; contexto de lo
    // mostrado; evidencia del análisis aparte. `raw` (el JSON entero de la API)
    // deja de persistirse: con 5 playlists + vetas de 2.000 eran miles de filas
    // de varios KB leídas enteras en cada búsqueda.
    this.version(3)
      .stores({
        tracks:
          'crateId, status, entity.year, updatedAt, *entity.genres, *sourceIds, *tags, shown.queryText, shown.sessionId',
        analyses: 'crateId',
      })
      .upgrade((tx) =>
        tx
          .table('tracks')
          .toCollection()
          .modify((t: Partial<CrateRow>) => {
            const fuentes = (t.sources ?? []).map(sinRaw)
            t.sources = fuentes
            t.sourceIds = fuentes.map((s) => s.id)
            t.tags = t.tags ?? []
          }),
      )
    // v4: índice multiEntry por contexto saltado ("no para esta búsqueda"),
    // para que la búsqueda lo consulte sin leer la tabla. Versión aparte de v3
    // porque un crate ya abierto en v3 no rehace los índices sin subir de versión.
    this.version(4).stores({
      tracks:
        'crateId, status, entity.year, updatedAt, *entity.genres, *sourceIds, *tags, *skippedFor, shown.queryText, shown.sessionId',
    })
  }
}

export const db = new CrateDB()

const stamp = (): string => new Date().toISOString()

function sinRaw(s: SourceItem): SourceItem {
  if (s.raw === undefined) return s
  const { raw: _raw, ...resto } = s
  return resto
}

/** Completa lo que necesitan los índices antes de escribir. */
function conIndices(t: EnrichedTrack, extra: Partial<CrateRow> = {}): CrateRow {
  const sources = t.sources.map(sinRaw)
  const { pending: _pending, ...ficha } = t
  return {
    ...ficha,
    ...extra,
    sources,
    sourceIds: sources.map((s) => s.id),
    tags: extra.tags ?? t.tags ?? [],
  }
}

/**
 * Registra un track como visto, con el contexto en que se mostró. No pisa un
 * saved/analyzed/rejected existente, pero sí actualiza su `shown`: que algo
 * ya guardado vuelva a aparecer en otra búsqueda cuenta como MOSTRADA para la
 * métrica (no como acierto: eso lo decide `savedAt` contra `shownAt`).
 */
export async function markSeen(track: EnrichedTrack, shown?: ShownContext): Promise<void> {
  const existing = await db.tracks.get(track.crateId)
  if (existing) {
    if (shown) await db.tracks.update(track.crateId, { shown })
    return
  }
  await db.tracks.put(conIndices({ ...track, status: 'seen' }, { shown }))
}

/**
 * "No para esta búsqueda": se oculta en ese contexto y nada más. No es
 * rechazo (no resta affinity): Thomas redistribuye entre listas, y un "no
 * encaja en 80s" no dice nada del disco.
 */
export async function skipFor(track: EnrichedTrack, queryText: string): Promise<void> {
  const existing = await db.tracks.get(track.crateId)
  const base = existing ?? conIndices({ ...track, status: 'seen' })
  const skippedFor = Array.from(new Set([...(base.skippedFor ?? []), queryText]))
  await db.tracks.put({ ...base, skippedFor, updatedAt: stamp() })
}

/**
 * Ids de FUENTE marcados "no para esta búsqueda" en ese contexto (el texto de
 * la query, o `veta:<nombre>`). La búsqueda los une a `knownSourceIds` para
 * que lo que dijiste que no va acá no vuelva a aparecer acá, aunque hideSeen
 * esté apagado. Va por el índice multiEntry: no lee las fichas.
 */
export async function skippedSourceIds(contexto: string): Promise<Set<string>> {
  const out = new Set<string>()
  await db.tracks
    .where('skippedFor')
    .equals(contexto)
    .each((t) => t.sourceIds.forEach((id) => out.add(id)))
  return out
}

/**
 * Todos los IDs que ya pasaron por el índice, en cualquier estado.
 * Incluye a propósito los saved y rejected: si ya lo guardaste lo tenés, y si lo
 * descartaste no lo querés ver. Es lo que alimenta "no me muestres lo que ya vi".
 */
export async function knownIds(): Promise<Set<string>> {
  const ids = (await db.tracks.toCollection().primaryKeys()) as string[]
  return new Set(ids)
}

/**
 * Ids de FUENTE ya vistos (el id de YouTube, no el crateId).
 * El crateId recién se conoce después de cruzar contra catálogo; el de la fuente
 * se sabe de entrada, así que permite descartar sin gastar red en enriquecer.
 * Va por el índice multiEntry: no lee las fichas.
 */
export async function knownSourceIds(): Promise<Set<string>> {
  const keys = (await db.tracks.orderBy('sourceIds').uniqueKeys()) as string[]
  return new Set(keys)
}

/**
 * Guarda un track en el crate. `tags` es la colección con que lo guardás desde
 * la app ("80s", "soul"): la misma taxonomía que las playlists importadas, así
 * el "match con tus discos de soul" vale también para lo guardado acá.
 */
export async function save(track: EnrichedTrack, opts: { tags?: string[] } = {}): Promise<Affinity> {
  const existing = await db.tracks.get(track.crateId)
  const alreadyInCrate = existing?.status === 'saved' || existing?.status === 'analyzed'
  const tags = Array.from(new Set([...(existing?.tags ?? []), ...(track.tags ?? []), ...(opts.tags ?? [])]))
  const now = stamp()
  const fila = conIndices(
    { ...track, status: existing?.status === 'analyzed' ? 'analyzed' : 'saved', updatedAt: now },
    {
      tags,
      shown: existing?.shown,
      skippedFor: existing?.skippedFor,
      savedAt: alreadyInCrate ? existing?.savedAt : now,
    },
  )
  await db.tracks.put(fila)
  return alreadyInCrate ? getAffinity() : bumpAffinity(fila, +1)
}

/**
 * Guarda un track importado de una playlist, sumándole el tag.
 *
 * Los tags se acumulan pero la affinity NO: si el mismo tema está en JAZZ y en
 * JAZZ FUSION, eso es solapamiento de categorías, no que te guste el doble.
 * Un track = un +1, sin importar en cuántas playlists aparezca.
 */
export async function saveFromPlaylist(track: EnrichedTrack, tag: string): Promise<void> {
  await db.transaction('rw', db.tracks, db.meta, async () => {
    const existing = await db.tracks.get(track.crateId)
    const base = existing ?? track
    const tags = Array.from(new Set([...(base.tags ?? []), tag]))
    const alreadyInCrate = existing?.status === 'saved' || existing?.status === 'analyzed'
    const now = stamp()

    const fila = conIndices(
      {
        ...base,
        status: existing?.status === 'analyzed' ? 'analyzed' : 'saved',
        updatedAt: now,
      },
      { tags, savedAt: alreadyInCrate ? existing?.savedAt : now },
    )
    await db.tracks.put(fila)
    if (!alreadyInCrate) await bumpAffinity(fila, +1)
  })
}

/**
 * La fila que queda al sacar/rechazar: la ficha en memoria (la del pipeline,
 * sin `shown`/`tags`/`skippedFor`) fusionada sobre la persistida, para no
 * perder el contexto en que se mostró ni la colección. Sin esto el hit rate
 * nunca veía un rechazo (la ficha rechazada perdía `shown`) y el -1 de
 * affinity no descontaba los tags que el +1 había sumado.
 */
async function filaAlSalir(track: EnrichedTrack, status: 'seen' | 'rejected'): Promise<CrateRow> {
  const existing = await db.tracks.get(track.crateId)
  const { savedAt: _savedAt, ...base } = existing ?? {}
  return conIndices(
    { ...base, ...track, status, updatedAt: stamp() },
    { shown: existing?.shown, tags: existing?.tags ?? track.tags, skippedFor: existing?.skippedFor },
  )
}

/**
 * Saca un track del crate y revierte exactamente el +1 que sumó al guardarlo.
 * No es lo mismo que rechazar: vuelve a neutral en vez de restar interés.
 */
export async function remove(track: EnrichedTrack): Promise<Affinity> {
  const fila = await filaAlSalir(track, 'seen')
  await db.tracks.put(fila)
  return bumpAffinity(fila, -1)
}

export async function reject(track: EnrichedTrack): Promise<Affinity> {
  const fila = await filaAlSalir(track, 'rejected')
  await db.tracks.put(fila)
  return bumpAffinity(fila, -1)
}

/**
 * Fusiona el resultado del análisis de audio como metadata propia (con provenance).
 *
 * El BPM se pliega a la octava del oído del usuario (`tempo.ts`), pero sin
 * mezclar: el valor plegado va a la ficha como `inferred` con su razón, y el
 * crudo, las alternativas y la ventana quedan en `analyses` como `analyzed`.
 * Si el DSP ya cae en el rango, la ficha lleva el analizado tal cual.
 *
 * Suma a la affinity solo si el track no estaba ya en el crate (mismo criterio
 * que `saveFromPlaylist`): analizar algo guardado no es guardarlo dos veces.
 * Si ya estaba, aprende igual el DATO nuevo: el bucket de BPM (descontando el
 * que la ficha tenía, si `learn` lo había contado).
 */
export async function saveAnalysis(
  track: EnrichedTrack,
  result: AnalyzeResult,
): Promise<EnrichedTrack> {
  const existing = await db.tracks.get(track.crateId)
  const alreadyInCrate = existing?.status === 'saved' || existing?.status === 'analyzed'
  const affinity = await getAffinity()
  const prior = tasteTempoRange(affinity)

  let bpm = track.bpm
  let bpmRaw = existing?.bpmRaw ?? track.bpmRaw
  let analysis: TrackAnalysis | undefined
  const r = result.bpm as BpmResultConEvidencia | undefined
  if (r) {
    const crudo = analyzed(r.value, r.confidence)
    const fold = foldBpm(r.value, r.alternatives, prior, { confidence: r.confidence })
    bpm = fold.folded
      ? prov(fold.value, 'audio_analysis', 'inferred', r.confidence * 0.9)
      : crudo
    // el crudo viaja en la ficha solo cuando difiere de lo que se muestra
    bpmRaw = fold.folded ? crudo : undefined
    analysis = {
      crateId: track.crateId,
      bpmRaw: crudo,
      alternatives: r.alternatives,
      ambiguous: r.ambiguous,
      window: r.window,
      folded: fold.folded,
      prior,
      reason: fold.reason,
      updatedAt: stamp(),
    }
  }

  const now = stamp()
  const merged: EnrichedTrack = {
    ...track,
    bpm,
    bpmRaw,
    key: result.key ? analyzed(result.key.value, result.key.confidence) : track.key,
    instruments: result.instruments
      ? analyzed(result.instruments.value, result.instruments.confidence)
      : track.instruments,
    status: track.status === 'saved' ? 'saved' : 'analyzed',
    updatedAt: now,
  }
  const fila = conIndices(merged, {
    tags: existing?.tags ?? merged.tags,
    shown: existing?.shown,
    skippedFor: existing?.skippedFor,
    savedAt: alreadyInCrate ? existing?.savedAt : now,
  })
  await db.tracks.put(fila)
  if (analysis) await db.analyses.put(analysis)
  if (!alreadyInCrate) await bumpAffinity(fila, +1)
  else if (r) await bumpTempo(existing?.bpm, fila.bpm)
  return fila
}

/**
 * El usuario corrige la octava a mano (÷2 / ×2 en el AnalyzePanel). Se guarda
 * con provenance `user/manual`: es el dato que recalibra el prior de tempo, y
 * el único que de verdad mide el oído (el dataset de hoy lo corrigieron agentes).
 * Si la ficha está en el crate, la affinity descuenta el bucket viejo y suma el
 * nuevo; si no, lo aprende `save` cuando la guarde (el BPM manual cuenta).
 */
export async function setBpmManual(track: EnrichedTrack, value: number): Promise<EnrichedTrack> {
  const existing = await db.tracks.get(track.crateId)
  const previo = existing ?? track
  // el crudo del DSP queda a la vista aunque el usuario lo corrija
  const bpmRaw =
    previo.bpmRaw ??
    (previo.bpm?.source === 'audio_analysis' && previo.bpm.method === 'analyzed' ? previo.bpm : undefined)
  const merged: EnrichedTrack = {
    ...previo,
    bpm: prov(value, 'user', 'manual', 1),
    bpmRaw,
    updatedAt: stamp(),
  }
  const fila = conIndices(merged, {
    tags: existing?.tags ?? merged.tags,
    shown: existing?.shown,
    skippedFor: existing?.skippedFor,
    savedAt: existing?.savedAt,
  })
  await db.tracks.put(fila)
  const analysis = await db.analyses.get(track.crateId)
  if (analysis) await db.analyses.put({ ...analysis, folded: true, reason: 'corregido a mano', updatedAt: stamp() })
  const enCrate = existing?.status === 'saved' || existing?.status === 'analyzed'
  if (enCrate) await bumpTempo(existing?.bpm, fila.bpm)
  return fila
}

export async function getAnalysis(crateId: string): Promise<TrackAnalysis | undefined> {
  return db.analyses.get(crateId)
}

/** El crate real: lo que guardaste o analizaste. Con `tag`, solo esa colección. */
export async function getCrate(tag?: string): Promise<EnrichedTrack[]> {
  const enCrate = (t: CrateRow): boolean => t.status === 'saved' || t.status === 'analyzed'
  if (tag) return db.tracks.where('tags').equals(tag).and(enCrate).toArray()
  return db.tracks.where('status').anyOf('saved', 'analyzed').toArray()
}

/** Tus colecciones con cuántas fichas tiene cada una. */
export async function getTags(): Promise<Record<string, number>> {
  const out: Record<string, number> = {}
  for (const t of await getCrate()) for (const tag of t.tags ?? []) out[tag] = (out[tag] ?? 0) + 1
  return out
}

/** Hit rate de una búsqueda o sesión: de lo que se mostró, cuánto quedó en el crate. */
export interface HitRate {
  mostradas: number
  guardadas: number
  rechazadas: number
  /** guardadas / mostradas; NaN si no se mostró nada */
  tasa: number
}

/**
 * Cuenta como acierto solo lo decidido DESPUÉS de mostrado en ese contexto:
 * una ficha que ya estaba en el crate (importada de playlist, guardada en otra
 * búsqueda) y reaparece con hideSeen apagado es "mostrada", no "guardada" de
 * esta búsqueda. Sin esto, 12 importadas entre 24 resultados daban 50% de hit
 * rate sin haber guardado nada nuevo. Filas viejas sin `savedAt` caen a
 * `updatedAt` (el save lo escribe).
 */
function contar(filas: CrateRow[]): HitRate {
  const despuesDeMostrada = (t: CrateRow, cuando: string | undefined): boolean =>
    !t.shown?.shownAt || (cuando != null && cuando > t.shown.shownAt)
  const guardadas = filas.filter(
    (t) => (t.status === 'saved' || t.status === 'analyzed') && despuesDeMostrada(t, t.savedAt ?? t.updatedAt),
  ).length
  const rechazadas = filas.filter((t) => t.status === 'rejected' && despuesDeMostrada(t, t.updatedAt)).length
  return { mostradas: filas.length, guardadas, rechazadas, tasa: guardadas / filas.length }
}

/**
 * Hit rate por texto de búsqueda (todas las veces que se corrió) o por sesión.
 * Es la métrica del producto (el 53% medido a mano el 19-sep), calculada por
 * la app sobre uso real y no sobre un fixture congelado.
 */
export async function hitRate(por: { queryText: string } | { sessionId: string }): Promise<HitRate> {
  const filas =
    'queryText' in por
      ? await db.tracks.where('shown.queryText').equals(por.queryText).toArray()
      : await db.tracks.where('shown.sessionId').equals(por.sessionId).toArray()
  return contar(filas)
}

/** Hit rate de cada búsqueda que se corrió, ordenado por cantidad mostrada. */
export async function hitRatePorQuery(): Promise<Array<HitRate & { queryText: string }>> {
  const porQuery = new Map<string, CrateRow[]>()
  await db.tracks
    .where('shown.queryText')
    .notEqual('')
    .each((t) => {
      const q = t.shown?.queryText
      if (!q) return
      porQuery.set(q, [...(porQuery.get(q) ?? []), t])
    })
  return [...porQuery.entries()]
    .map(([queryText, filas]) => ({ queryText, ...contar(filas) }))
    .sort((a, b) => b.mostradas - a.mostradas)
}

export async function getAffinity(): Promise<Affinity> {
  const row = await db.meta.get('affinity')
  // los crates guardados antes de que existiera un contador nuevo no lo traen
  return { ...emptyAffinity(), ...((row?.value as Partial<Affinity> | undefined) ?? {}) }
}

async function bumpAffinity(track: EnrichedTrack, weight: number): Promise<Affinity> {
  const current = await getAffinity()
  const next = learn(current, track, weight)
  await db.meta.put({ key: 'affinity', value: next })
  return next
}

/** Solo el tempo cambió en una ficha que ya está en el crate: -1 al bucket viejo, +1 al nuevo. */
async function bumpTempo(
  oldBpm: Provenanced<number> | undefined,
  newBpm: Provenanced<number> | undefined,
): Promise<Affinity> {
  const next = learnBpmOnly(await getAffinity(), oldBpm, newBpm)
  await db.meta.put({ key: 'affinity', value: next })
  return next
}
