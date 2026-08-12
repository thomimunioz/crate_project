import { useMemo, useState } from 'react'
import type { EnrichedTrack } from '@/core/entities'
import { useCrate } from '@/state/useCrateStore'
import { ResultCard } from './ResultCard'
import { PlaylistImport } from './PlaylistImport'
import { Vetas } from './Vetas'

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
    ...(t.tags ?? []),
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
}

/** Un número del tablero del crate. */
function Cifra({ n, label }: { n: number; label: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[17px] font-bold leading-none tabular-nums">{n}</span>
      <span className="text-[9px] uppercase tracking-[0.16em] text-crate-lcdInk/55">{label}</span>
    </div>
  )
}

/** Tu crate: lo que guardaste o analizaste. Filtra local, sin tocar la red. */
export function CrateView() {
  const { crateTracks } = useCrate()
  const [filter, setFilter] = useState('')
  // las herramientas de siembra ocupan lugar: se abren cuando hacen falta
  const [sembrando, setSembrando] = useState(false)

  const shown = useMemo(() => {
    const q = filter.trim().toLowerCase()
    if (!q) return crateTracks
    return crateTracks.filter((t) => haystack(t).includes(q))
  }, [crateTracks, filter])

  const analyzed = crateTracks.filter((t) => t.status === 'analyzed').length
  const confirmados = crateTracks.filter((t) => t.entity.confirmed).length

  // tus tags, ordenados por cuántos temas tienen cada uno
  const tagCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const t of crateTracks) for (const tag of t.tags ?? []) {
      counts.set(tag, (counts.get(tag) ?? 0) + 1)
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1])
  }, [crateTracks])

  if (crateTracks.length === 0) {
    return (
      <div className="flex flex-col gap-4">
        <div className="panel flex flex-col items-center gap-3 px-6 py-10 text-center">
          {/* cajón vacío: tres fichas dibujadas esperando */}
          <div aria-hidden className="flex items-end gap-1">
            <span className="h-8 w-6 rounded-sm border border-crate-line bg-crate-panel2" />
            <span className="h-10 w-6 -rotate-2 rounded-sm border border-crate-line bg-crate-card" />
            <span className="h-9 w-6 rotate-1 rounded-sm border border-crate-line bg-crate-panel2" />
          </div>
          <p className="font-display text-lg text-crate-soft">Tu crate está vacío.</p>
          <p className="max-w-sm text-sm text-crate-faint">
            Guardá algo con <span className="text-crate-go">♡</span> desde una búsqueda, o sembralo
            con una playlist tuya: cada playlist te deja su nombre como etiqueta.
          </p>
        </div>
        <PlaylistImport />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {/* tablero del crate */}
      <div className="lcd flex flex-wrap items-center gap-x-5 gap-y-3 px-4 py-3 sm:gap-x-7">
        <Cifra n={crateTracks.length} label="fichas" />
        <Cifra n={confirmados} label="confirmadas" />
        <Cifra n={analyzed} label="analizadas" />
        {filter && <Cifra n={shown.length} label="coinciden" />}
        <button
          onClick={() => setSembrando((v) => !v)}
          aria-expanded={sembrando}
          className="ml-auto rounded border border-crate-lcdInk/40 px-2.5 py-1.5 font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-crate-lcdInk transition-colors hover:border-crate-lcdInk hover:bg-crate-lcdInk/10"
        >
          {sembrando ? '− sembrar' : '+ sembrar'}
        </button>
      </div>

      {sembrando && (
        <div className="flex flex-col gap-4">
          <Vetas />
          <PlaylistImport />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="filtrar por artista, sello, instrumento…"
          aria-label="Filtrar tu crate"
          className="field max-w-xs flex-1 py-1.5 text-sm"
        />
        {filter && (
          <button onClick={() => setFilter('')} className="chip-btn">
            limpiar ✕
          </button>
        )}
      </div>

      {tagCounts.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          <span className="eyebrow mr-1 self-center">etiquetas</span>
          {tagCounts.map(([tag, n]) => (
            <button
              key={tag}
              onClick={() => setFilter(filter === tag ? '' : tag)}
              aria-pressed={filter === tag}
              className={`chip-btn ${filter === tag ? 'chip-on' : 'text-crate-soft'}`}
            >
              #{tag} <span className="text-crate-faint">{n}</span>
            </button>
          ))}
        </div>
      )}

      {shown.length === 0 ? (
        <p className="text-crate-soft">Nada en tu crate coincide con «{filter}».</p>
      ) : (
        <div className="flex flex-col gap-3">
          {shown.map((t) => (
            <ResultCard key={t.crateId} track={t} />
          ))}
        </div>
      )}
    </div>
  )
}
