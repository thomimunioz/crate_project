/**
 * Store principal (Zustand): query, resultados, affinity y acciones.
 * Ata el pipeline (Capa 1) con el crate-index (Dexie) y el backend (Capa 2).
 */
import { create } from 'zustand'
import type { EnrichedTrack, SearchQuery } from '@/core/entities'
import type { Affinity } from '@/core/affinity'
import { emptyAffinity } from '@/core/affinity'
import { runSearch, importPlaylist } from '@/pipeline'
import { parsePlaylistId } from '@/sources/youtube'
import * as crate from '@/db/crateIndex'
import { purgeExpired } from '@/db/cache'
import { analyzeAudio } from '@/api/backend'

export type View = 'search' | 'crate'

interface CrateState {
  view: View
  query: SearchQuery
  results: EnrichedTrack[]
  /** el crate real: saved + analyzed. Se carga on demand. */
  crateTracks: EnrichedTrack[]
  loading: boolean
  analyzing: string | null
  /** progreso del import; null si no hay uno corriendo */
  importing: { label: string; done: number; total: number } | null
  error?: string
  affinity: Affinity
  hideSeen: boolean
  ready: boolean

  init: () => Promise<void>
  setView: (v: View) => Promise<void>
  patchQuery: (q: Partial<SearchQuery>) => void
  search: () => Promise<void>
  loadCrate: () => Promise<void>
  importPlaylists: (input: string) => Promise<void>
  save: (t: EnrichedTrack) => Promise<void>
  remove: (t: EnrichedTrack) => Promise<void>
  reject: (t: EnrichedTrack) => Promise<void>
  analyze: (t: EnrichedTrack) => Promise<void>
  toggleHideSeen: () => void
}

export const useCrate = create<CrateState>((set, get) => ({
  view: 'search',
  query: { text: '' },
  results: [],
  crateTracks: [],
  loading: false,
  analyzing: null,
  importing: null,
  affinity: emptyAffinity(),
  hideSeen: true,
  ready: false,

  async init() {
    void purgeExpired() // en background: no vale la pena bloquear el arranque
    const affinity = await crate.getAffinity()
    set({ affinity, ready: true })
    await get().loadCrate()
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
          failed.push(`${id}: ${e instanceof Error ? e.message : String(e)}`)
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
    const crateTracks = await crate.getCrate()
    crateTracks.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
    set({ crateTracks })
  },

  async search() {
    const { query, affinity, hideSeen } = get()
    if (!query.text.trim()) return
    set({ loading: true, error: undefined })
    try {
      const known = await crate.knownIds() // capturar ANTES de marcar
      let results = await runSearch(query, affinity)
      await Promise.all(results.map((t) => crate.markSeen(t)))
      if (hideSeen) results = results.filter((t) => !known.has(t.crateId))
      set({ results })
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e) })
    } finally {
      set({ loading: false })
    }
  },

  async save(t) {
    const affinity = await crate.save(t)
    const saved: EnrichedTrack = { ...t, status: 'saved' }
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

  async analyze(t) {
    const src = t.sources[0]
    if (!src) return
    set({ analyzing: t.crateId })
    try {
      const result = await analyzeAudio(src.url)
      const merged = await crate.saveAnalysis(t, result)
      set({
        results: get().results.map((r) => (r.crateId === t.crateId ? merged : r)),
        crateTracks: get().crateTracks.map((r) => (r.crateId === t.crateId ? merged : r)),
      })
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e) })
    } finally {
      set({ analyzing: null })
    }
  },

  toggleHideSeen() {
    set({ hideSeen: !get().hideSeen })
  },
}))
