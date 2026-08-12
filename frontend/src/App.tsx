import { useEffect } from 'react'
import { useCrate, type View } from '@/state/useCrateStore'
import { FilterBar } from '@/ui/components/FilterBar'
import { ResultCard } from '@/ui/components/ResultCard'
import { CrateView } from '@/ui/components/CrateView'

/** Selector de vista, con pinta de switch de consola. */
function Tab({ id, label, count }: { id: View; label: string; count?: number }) {
  const { view, setView } = useCrate()
  const active = view === id
  return (
    <button
      onClick={() => void setView(id)}
      aria-pressed={active}
      className={`flex items-center gap-1.5 rounded px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-[0.12em] transition-colors ${
        active
          ? 'bg-crate-amber/15 text-crate-amber'
          : 'text-crate-faint hover:bg-crate-panel2 hover:text-crate-soft'
      }`}
    >
      <span className={`led ${active ? 'led-on' : ''}`} />
      {label}
      {count != null && count > 0 && (
        <span className={active ? 'text-crate-amber/70' : 'text-crate-faint'}>{count}</span>
      )}
    </button>
  )
}

/**
 * Transporte de la consola: qué está haciendo el motor ahora mismo.
 * Determinado cuando sabemos cuántas fichas faltan cruzar; barrido si no.
 */
function Transporte() {
  const { loading, enriching, mining } = useCrate()
  if (!loading && !mining) return null

  const total = enriching?.total ?? 0
  const done = enriching?.done ?? 0
  const pct = total > 0 ? Math.round((done / total) * 100) : 0

  return (
    <div className="lcd px-3 py-2" role="status" aria-live="polite">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.14em]">
        <span className="led led-on animate-pulse" />
        {mining ? (
          <span>⛏ minando el canal · {mining}</span>
        ) : total > 0 ? (
          <span>cruzando contra catálogo</span>
        ) : (
          <span>diggeando…</span>
        )}
        {total > 0 && (
          <span className="ml-auto font-bold tabular-nums">
            {done}/{total}
          </span>
        )}
      </div>

      {total > 0 ? (
        <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-black/50">
          <div
            className="h-full bg-crate-lcdInk transition-[width] duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
      ) : (
        <div className="scanbar mt-2" />
      )}
    </div>
  )
}

function SearchView() {
  const { results, loading } = useCrate()
  const cruzadas = results.filter((t) => !t.pending).length

  return (
    <>
      <FilterBar />

      <Transporte />

      {results.length > 0 && (
        <p className="eyebrow">
          {results.length} fichas
          {cruzadas < results.length && ` · ${cruzadas} cruzando`}
        </p>
      )}

      {!loading && results.length === 0 && (
        <div className="panel flex flex-col items-center gap-3 px-6 py-10 text-center">
          {/* el disco esperando que alguien lo saque del cajón */}
          <div
            aria-hidden
            className="grid h-16 w-16 animate-spin-slow place-items-center rounded-full border border-crate-line bg-crate-panel2"
          >
            <span className="grid h-6 w-6 place-items-center rounded-full border border-crate-dust">
              <span className="h-1.5 w-1.5 rounded-full bg-crate-dust" />
            </span>
          </div>
          <p className="font-display text-lg text-crate-soft">El cajón está cerrado.</p>
          <p className="max-w-sm text-sm text-crate-faint">
            Escribí una escena, una época o un instrumento y dale a{' '}
            <span className="font-mono text-crate-amber">DIG</span>. Cuanto más específico, más
            hondo cava.
          </p>
        </div>
      )}

      <div className="flex flex-col gap-3">
        {results.map((t) => (
          // clave de la FUENTE: el crateId cambia cuando el cruce identifica la obra
          <ResultCard key={t.sources[0]?.id ?? t.crateId} track={t} />
        ))}
      </div>
    </>
  )
}

export default function App() {
  const { view, error, crateTracks, init } = useCrate()

  useEffect(() => {
    void init()
  }, [init])

  return (
    <div className="relative min-h-full">
      {/* grano cinematográfico sobre todo, sin tocar los eventos */}
      <div aria-hidden className="grain-overlay pointer-events-none fixed inset-0 z-50 opacity-60" />

      <header className="sticky top-0 z-40 border-b border-crate-line bg-crate-bg/90 backdrop-blur-sm">
        <div className="pt-safe mx-auto flex max-w-4xl items-center justify-between gap-3 px-4 pb-3">
          <div className="flex items-center gap-3">
            <div className="lcd px-2.5 py-1 text-lg font-bold tracking-[0.22em] animate-flicker sm:text-xl">
              CRATE<span className="text-crate-amber">.</span>
            </div>
            <p className="eyebrow hidden text-crate-dust sm:block">
              dig deeper — find what nobody else found
            </p>
          </div>
          <nav
            aria-label="Vistas"
            className="flex flex-none rounded-md border border-crate-line bg-crate-panel p-0.5"
          >
            <Tab id="search" label="buscar" />
            <Tab id="crate" label="tu crate" count={crateTracks.length} />
          </nav>
        </div>
      </header>

      <main className="pb-safe mx-auto flex max-w-4xl flex-col gap-4 px-4 pt-4">
        {error && (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-md border border-crate-stop/50 bg-crate-stop/10 px-4 py-3 text-sm text-crate-stop"
          >
            <span aria-hidden className="font-mono">
              ⚠
            </span>
            <span>{error}</span>
          </div>
        )}

        {view === 'search' ? <SearchView /> : <CrateView />}

        <footer className="perf mt-4 pt-4 text-center">
          <p className="eyebrow text-crate-dust">the internet is the crate</p>
        </footer>
      </main>
    </div>
  )
}
