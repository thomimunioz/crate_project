import { useEffect } from 'react'
import { useCrate } from '@/state/useCrateStore'
import { FilterBar } from '@/ui/components/FilterBar'
import { ResultCard } from '@/ui/components/ResultCard'

export default function App() {
  const { results, loading, error, hideSeen, toggleHideSeen, init } = useCrate()

  useEffect(() => {
    void init()
  }, [init])

  return (
    <div className="mx-auto flex min-h-full max-w-3xl flex-col gap-6 px-4 py-8">
      <header className="flex items-end justify-between">
        <div>
          <div className="lcd inline-block px-3 py-1.5 text-2xl font-bold tracking-widest">
            CRATE<span className="text-crate-amber">.</span>
          </div>
          <p className="eyebrow mt-2">the internet is the crate — dig deeper</p>
        </div>
        <button
          onClick={toggleHideSeen}
          className="chip"
          title="No mostrar lo que ya viste en búsquedas anteriores"
        >
          {hideSeen ? '🙈 ocultando vistos' : '👁 mostrando todo'}
        </button>
      </header>

      <FilterBar />

      {error && (
        <div className="rounded-md border border-crate-stop/50 bg-crate-stop/10 px-4 py-3 text-sm text-crate-stop">
          {error}
        </div>
      )}

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
    </div>
  )
}
