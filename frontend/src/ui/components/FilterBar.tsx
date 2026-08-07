import { useState } from 'react'
import { useCrate } from '@/state/useCrateStore'

/** Filtros estructurados. Diseñado para que a futuro entre lenguaje natural (ver docs/TAXONOMY.md). */
export function FilterBar() {
  const { query, patchQuery, search, loading } = useCrate()
  const [advanced, setAdvanced] = useState(false)

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    void search()
  }

  const setList = (key: 'genres' | 'instruments', raw: string) =>
    patchQuery({ [key]: raw ? raw.split(',').map((s) => s.trim()).filter(Boolean) : undefined })

  const setRange = (key: 'bpm' | 'year', lo: string, hi: string) => {
    if (!lo && !hi) return patchQuery({ [key]: undefined })
    patchQuery({ [key]: [Number(lo) || 0, Number(hi) || 9999] })
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3">
      <div className="flex gap-2">
        <input
          value={query.text}
          onChange={(e) => patchQuery({ text: e.target.value })}
          placeholder="soul jazz rhodes 75-90 bpm minor…"
          className="flex-1 rounded-md border border-crate-line bg-crate-panel px-4 py-3 text-crate-ink placeholder:text-crate-faint focus:border-crate-amber focus:outline-none"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-crate-amber px-5 py-3 font-mono text-sm font-bold text-crate-bg disabled:opacity-50"
        >
          DIG
        </button>
      </div>

      <button
        type="button"
        onClick={() => setAdvanced((v) => !v)}
        className="eyebrow self-start hover:text-crate-amber"
      >
        {advanced ? '− filtros' : '+ filtros'}
      </button>

      {advanced && (
        <div className="grid grid-cols-2 gap-3 rounded-md border border-crate-line bg-crate-panel/50 p-3 sm:grid-cols-4">
          <label className="flex flex-col gap-1 text-xs text-crate-soft">
            Géneros
            <input
              onChange={(e) => setList('genres', e.target.value)}
              placeholder="Soul, MPB"
              className="rounded border border-crate-line bg-crate-bg px-2 py-1.5 text-crate-ink"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-crate-soft">
            Instrumentos
            <input
              onChange={(e) => setList('instruments', e.target.value)}
              placeholder="Rhodes, strings"
              className="rounded border border-crate-line bg-crate-bg px-2 py-1.5 text-crate-ink"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-crate-soft">
            BPM
            <div className="flex items-center gap-1">
              <input
                id="bpmLo"
                type="number"
                placeholder="70"
                className="w-full rounded border border-crate-line bg-crate-bg px-2 py-1.5 text-crate-ink"
                onChange={(e) =>
                  setRange('bpm', e.target.value, (document.getElementById('bpmHi') as HTMLInputElement)?.value)
                }
              />
              <span className="text-crate-faint">–</span>
              <input
                id="bpmHi"
                type="number"
                placeholder="90"
                className="w-full rounded border border-crate-line bg-crate-bg px-2 py-1.5 text-crate-ink"
                onChange={(e) =>
                  setRange('bpm', (document.getElementById('bpmLo') as HTMLInputElement)?.value, e.target.value)
                }
              />
            </div>
          </label>
          <label className="flex flex-col gap-1 text-xs text-crate-soft">
            Década
            <input
              placeholder="1970-1979"
              className="rounded border border-crate-line bg-crate-bg px-2 py-1.5 text-crate-ink"
              onChange={(e) => {
                const [lo, hi] = e.target.value.split('-')
                setRange('year', lo ?? '', hi ?? '')
              }}
            />
          </label>
        </div>
      )}
    </form>
  )
}
