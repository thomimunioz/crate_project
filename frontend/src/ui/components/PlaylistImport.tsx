import { useState } from 'react'
import { useCrate } from '@/state/useCrateStore'

/**
 * Import de una playlist propia de YouTube como semilla del crate.
 * Cuesta ~1 unidad de quota cada 50 temas, contra las 100 que cuesta una búsqueda.
 */
export function PlaylistImport() {
  const { importPlaylist, importing } = useCrate()
  const [url, setUrl] = useState('')

  const busy = importing !== null
  const pct = importing && importing.total > 0 ? (importing.done / importing.total) * 100 : 0

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!busy) void importPlaylist(url)
  }

  return (
    <form onSubmit={onSubmit} className="rounded-xl border border-crate-line bg-crate-panel p-4">
      <p className="eyebrow">sembrar el crate</p>
      <p className="mt-1 text-sm text-crate-soft">
        Pegá una playlist tuya de YouTube. Los temas que ya elegiste a mano son la mejor señal
        para que CRATE aprenda tu oído.
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={busy}
          placeholder="https://www.youtube.com/playlist?list=…"
          className="min-w-0 flex-1 rounded-md border border-crate-line bg-crate-bg px-3 py-1.5 text-sm placeholder:text-crate-faint focus:border-crate-amber focus:outline-none disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={busy || !url.trim()}
          className="chip hover:border-crate-amber disabled:opacity-50"
        >
          {busy ? 'importando…' : 'importar'}
        </button>
      </div>

      {importing && (
        <div className="mt-3">
          <div className="h-1 w-full overflow-hidden rounded-full bg-crate-bg">
            <div
              className="h-full bg-crate-amber transition-all duration-300"
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="eyebrow mt-1.5">
            {importing.total === 0
              ? 'leyendo la playlist…'
              : `cruzando contra Discogs · ${importing.done} de ${importing.total}`}
          </p>
        </div>
      )}
    </form>
  )
}
