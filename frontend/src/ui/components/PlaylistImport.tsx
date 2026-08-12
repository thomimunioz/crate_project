import { useState } from 'react'
import { useCrate } from '@/state/useCrateStore'

/**
 * Import de playlists propias de YouTube como semilla del crate.
 * Cuesta ~1 unidad de quota cada 50 temas, contra las 100 de una sola búsqueda.
 */
export function PlaylistImport() {
  const { importPlaylists, importing } = useCrate()
  const [urls, setUrls] = useState('')

  const busy = importing !== null
  const pct = importing && importing.total > 0 ? (importing.done / importing.total) * 100 : 0

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!busy) void importPlaylists(urls)
  }

  return (
    <form onSubmit={onSubmit} className="panel p-4">
      <div className="flex items-center gap-2">
        <span className="tape">sembrar el crate</span>
        <span className="eyebrow">playlists tuyas</span>
      </div>
      <p className="mt-2.5 text-sm text-crate-soft">
        Pegá playlists tuyas de YouTube, una por línea. El nombre de cada una queda como etiqueta:
        es tu forma de agrupar, aparte de lo que diga el catálogo.
      </p>

      <textarea
        value={urls}
        onChange={(e) => setUrls(e.target.value)}
        disabled={busy}
        rows={3}
        aria-label="URLs de playlists de YouTube, una por línea"
        placeholder={'https://www.youtube.com/playlist?list=…\nhttps://www.youtube.com/playlist?list=…'}
        className="field mt-3 resize-y font-mono text-xs disabled:opacity-50"
      />

      <div className="mt-2 flex justify-end">
        <button type="submit" disabled={busy || !urls.trim()} className="btn">
          {busy ? 'importando…' : 'importar'}
        </button>
      </div>

      {importing && (
        <div className="lcd mt-3 px-3 py-2" role="status" aria-live="polite">
          <p className="flex items-center gap-2 text-[11px] uppercase tracking-[0.14em]">
            <span className="led led-on animate-pulse" />
            <span className="truncate">{importing.label}</span>
            {importing.total > 0 && (
              <span className="ml-auto font-bold tabular-nums">
                {importing.done}/{importing.total}
              </span>
            )}
          </p>
          {importing.total === 0 ? (
            <div className="scanbar mt-2" />
          ) : (
            <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-black/50">
              <div
                className="h-full bg-crate-lcdInk transition-[width] duration-300"
                style={{ width: `${pct}%` }}
              />
            </div>
          )}
          <p className="mt-1.5 text-[10px] text-crate-lcdInk/55">
            {importing.total === 0 ? 'leyendo la playlist…' : 'cruzando contra catálogo'}
          </p>
        </div>
      )}
    </form>
  )
}
