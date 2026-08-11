/**
 * Crate-index local en IndexedDB (Dexie). Estados: seen / saved / analyzed / rejected.
 * El crate real = saved + analyzed. `seen` habilita "no me muestres lo que ya vi".
 * Ver docs/ENTITY_MODEL.md
 */
import Dexie, { type Table } from 'dexie'
import type { EnrichedTrack } from '@/core/entities'
import type { Affinity } from '@/core/affinity'
import { emptyAffinity, learn } from '@/core/affinity'
import type { AnalyzeResult } from '@/api/backend'
import type { CacheRow } from './cache'
import { analyzed } from '@/core/provenance'

class CrateDB extends Dexie {
  tracks!: Table<EnrichedTrack, string>
  meta!: Table<{ key: string; value: unknown }, string>
  cache!: Table<CacheRow, string>

  constructor() {
    super('crate')
    this.version(1).stores({
      // índices: pk crateId, filtrables status/year/updatedAt, multiEntry en géneros
      tracks: 'crateId, status, entity.year, updatedAt, *entity.genres',
      meta: 'key',
    })
    // v2: cache de catálogo (Discogs/MusicBrainz). Ver db/cache.ts
    this.version(2).stores({ cache: 'key, expiresAt' })
  }
}

export const db = new CrateDB()

const stamp = (): string => new Date().toISOString()

/** Registra un track como visto (sin pisar un saved/analyzed existente). */
export async function markSeen(track: EnrichedTrack): Promise<void> {
  const existing = await db.tracks.get(track.crateId)
  if (existing) return
  await db.tracks.put({ ...track, status: 'seen' })
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
 */
export async function knownSourceIds(): Promise<Set<string>> {
  const all = await db.tracks.toArray()
  return new Set(all.flatMap((t) => t.sources.map((s) => s.id)))
}

export async function save(track: EnrichedTrack): Promise<Affinity> {
  await db.tracks.put({ ...track, status: 'saved', updatedAt: stamp() })
  return bumpAffinity(track, +1)
}

/**
 * Guarda un track importado de una playlist, sumándole el tag.
 *
 * Los tags se acumulan pero la affinity NO: si el mismo tema está en JAZZ y en
 * JAZZ FUSION, eso es solapamiento de categorías, no que te guste el doble.
 * Un track = un +1, sin importar en cuántas playlists aparezca.
 */
export async function saveFromPlaylist(track: EnrichedTrack, tag: string): Promise<void> {
  const existing = await db.tracks.get(track.crateId)
  const base = existing ?? track
  const tags = Array.from(new Set([...(base.tags ?? []), tag]))
  const alreadyInCrate = existing?.status === 'saved' || existing?.status === 'analyzed'

  await db.tracks.put({
    ...base,
    tags,
    status: existing?.status === 'analyzed' ? 'analyzed' : 'saved',
    updatedAt: stamp(),
  })
  if (!alreadyInCrate) await bumpAffinity(track, +1)
}

/**
 * Saca un track del crate y revierte exactamente el +1 que sumó al guardarlo.
 * No es lo mismo que rechazar: vuelve a neutral en vez de restar interés.
 */
export async function remove(track: EnrichedTrack): Promise<Affinity> {
  await db.tracks.put({ ...track, status: 'seen', updatedAt: stamp() })
  return bumpAffinity(track, -1)
}

export async function reject(track: EnrichedTrack): Promise<Affinity> {
  await db.tracks.put({ ...track, status: 'rejected', updatedAt: stamp() })
  return bumpAffinity(track, -1)
}

/** Fusiona el resultado del análisis de audio como metadata propia (con provenance). */
export async function saveAnalysis(
  track: EnrichedTrack,
  result: AnalyzeResult,
): Promise<EnrichedTrack> {
  const merged: EnrichedTrack = {
    ...track,
    bpm: result.bpm ? analyzed(result.bpm.value, result.bpm.confidence) : track.bpm,
    key: result.key ? analyzed(result.key.value, result.key.confidence) : track.key,
    instruments: result.instruments
      ? analyzed(result.instruments.value, result.instruments.confidence)
      : track.instruments,
    status: track.status === 'saved' ? 'saved' : 'analyzed',
    updatedAt: stamp(),
  }
  await db.tracks.put(merged)
  return merged
}

/** El crate real: lo que guardaste o analizaste. */
export async function getCrate(): Promise<EnrichedTrack[]> {
  return db.tracks.where('status').anyOf('saved', 'analyzed').toArray()
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
