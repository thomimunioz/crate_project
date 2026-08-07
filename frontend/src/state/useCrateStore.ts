/**
 * Store principal (Zustand): query, resultados, affinity y acciones.
 * Ata el pipeline (Capa 1) con el crate-index (Dexie) y el backend (Capa 2).
 */
import { create } from 'zustand'
import type { EnrichedTrack, SearchQuery } from '@/core/entities'
import type { Affinity } from '@/core/affinity'
import { emptyAffinity } from '@/core/affinity'
import { runSearch } from '@/pipeline'
import * as crate from '@/db/crateIndex'
import { purgeExpired } from '@/db/cache'
import { analyzeAudio } from '@/api/backend'

interface CrateState {
  query: SearchQuery
  results: EnrichedTrack[]
  loading: boolean
  analyzing: string | null
  error?: string
  affinity: Affinity
  hideSeen: boolean
  ready: boolean

  init: () => Promise<void>
  patchQuery: (q: Partial<SearchQuery>) => void
  search: () => Promise<void>
  save: (t: EnrichedTrack) => Promise<void>
  reject: (t: EnrichedTrack) => Promise<void>
  analyze: (t: EnrichedTrack) => Promise<void>
  toggleHideSeen: () => void
}

export const useCrate = create<CrateState>((set, get) => ({
  query: { text: '' },
  results: [],
  loading: false,
  analyzing: null,
  affinity: emptyAffinity(),
  hideSeen: true,
  ready: false,

  async init() {
    void purgeExpired() // en background: no vale la pena bloquear el arranque
    const affinity = await crate.getAffinity()
    set({ affinity, ready: true })
  },

  patchQuery(q) {
    set({ query: { ...get().query, ...q } })
  },

  async search() {
    const { query, affinity, hideSeen } = get()
    if (!query.text.trim()) return
    set({ loading: true, error: undefined })
    try {
      const seen = await crate.seenIds() // capturar ANTES de marcar
      let results = await runSearch(query, affinity)
      await Promise.all(results.map((t) => crate.markSeen(t)))
      if (hideSeen) results = results.filter((t) => !seen.has(t.crateId))
      set({ results })
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e) })
    } finally {
      set({ loading: false })
    }
  },

  async save(t) {
    const affinity = await crate.save(t)
    set({
      affinity,
      results: get().results.map((r) =>
        r.crateId === t.crateId ? { ...r, status: 'saved' } : r,
      ),
    })
  },

  async reject(t) {
    const affinity = await crate.reject(t)
    set({ affinity, results: get().results.filter((r) => r.crateId !== t.crateId) })
  },

  async analyze(t) {
    const src = t.sources[0]
    if (!src) return
    set({ analyzing: t.crateId })
    try {
      const result = await analyzeAudio(src.url)
      const merged = await crate.saveAnalysis(t, result)
      set({ results: get().results.map((r) => (r.crateId === t.crateId ? merged : r)) })
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
