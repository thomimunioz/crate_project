import { useMemo, useState } from 'react'
import type { EnrichedTrack } from '@/core/entities'
import { useCrate } from '@/state/useCrateStore'
import { ResultCard } from './ResultCard'
import { PlaylistImport } from './PlaylistImport'

/** Texto sobre el que filtra la búsqueda local: todo lo que sabemos del track. */
function haystack(t: EnrichedTrack): string {
  const e = t.entity
  return [
    e.artist,
    e.title,
    e.label,
    e.country,
    e.year,
    ...e.genres,
    ...e.styles,
    ...(t.instruments?.value ?? []),
    ...(t.mood?.value.feels ?? []),
    ...(t.mood?.value.textures ?? []),
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
}

/** Tu crate: lo que guardaste o analizaste. Filtra local, sin tocar la red. */
export function CrateView() {
  const { crateTracks } = useCrate()
  const [filter, setFilter] = useState('')

  const shown = useMemo(() => {
    const q = filter.trim().toLowerCase()
    if (!q) return crateTracks
    return crateTracks.filter((t) => haystack(t).includes(q))
  }, [crateTracks, filter])

  const analyzed = crateTracks.filter((t) => t.status === 'analyzed').length

  if (crateTracks.length === 0) {
    return (
      <div className="flex flex-col gap-4">
        <p className="text-crate-soft">
          Tu crate está vacío. Guardá algo con <span className="text-crate-amber">♡</span> desde
          una búsqueda, o arrancá importando una playlist tuya.
        </p>
        <PlaylistImport />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <PlaylistImport />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="eyebrow">
          {crateTracks.length} en el crate
          {analyzed > 0 && ` · ${analyzed} analizados`}
          {filter && ` · ${shown.length} coinciden`}
        </p>
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="filtrar por artista, sello, instrumento…"
          className="w-full max-w-xs rounded-md border border-crate-line bg-crate-panel px-3 py-1.5 text-sm placeholder:text-crate-faint focus:border-crate-amber focus:outline-none"
        />
      </div>

      {shown.length === 0 ? (
        <p className="text-crate-soft">Nada en tu crate coincide con «{filter}».</p>
      ) : (
        <div className="flex flex-col gap-4">
          {shown.map((t) => (
            <ResultCard key={t.crateId} track={t} />
          ))}
        </div>
      )}
    </div>
  )
}
