import { useEffect } from 'react'
import { useCrate, type View } from '@/state/useCrateStore'
import { FilterBar } from '@/ui/components/FilterBar'
import { ResultCard } from '@/ui/components/ResultCard'
import { CrateView } from '@/ui/components/CrateView'

function Tab({ id, label, count }: { id: View; label: string; count?: number }) {
  const { view, setView } = useCrate()
  const active = view === id
  return (
    <button
      onClick={() => void setView(id)}
      className={`chip ${active ? 'border-crate-amber text-crate-amber' : 'hover:border-crate-soft'}`}
    >
      {label}
      {count != null && count > 0 && <span className="text-crate-faint">{count}</span>}
    </button>
  )
}

function SearchView() {
  const { results, loading, hideSeen, toggleHideSeen } = useCrate()

  return (
    <>
      <div className="flex justify-end">
        <button
          onClick={toggleHideSeen}
          className="chip"
          title="No mostrar lo que ya viste en búsquedas anteriores"
        >
          {hideSeen ? '🙈 ocultando vistos' : '👁 mostrando todo'}
        </button>
      </div>

      <FilterBar />

      {loading && <p className="eyebrow animate-pulse">diggeando…</p>}

      {!loading && results.length === 0 && (
        <p className="text-crate-soft">
          Buscá algo tipo <code className="text-crate-amber">japanese city pop 1982</code> o{' '}
          <code className="text-crate-amber">70s brazilian MPB rhodes</code>.
        </p>
      )}

      <div className="flex flex-col gap-4">
        {results.map((t) => (
          <ResultCard key={t.crateId} track={t} />
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
    <div className="mx-auto flex min-h-full max-w-3xl flex-col gap-6 px-4 py-8">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="lcd inline-block px-3 py-1.5 text-2xl font-bold tracking-widest">
            CRATE<span className="text-crate-amber">.</span>
          </div>
          <p className="eyebrow mt-2">the internet is the crate — dig deeper</p>
        </div>
        <nav className="flex gap-1.5">
          <Tab id="search" label="buscar" />
          <Tab id="crate" label="tu crate" count={crateTracks.length} />
        </nav>
      </header>

      {error && (
        <div className="rounded-md border border-crate-stop/50 bg-crate-stop/10 px-4 py-3 text-sm text-crate-stop">
          {error}
        </div>
      )}

      {view === 'search' ? <SearchView /> : <CrateView />}
    </div>
  )
}
