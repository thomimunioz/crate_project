import { useCrate } from '@/state/useCrateStore'

/** Una veta se gana con al menos dos temas guardados: uno puede ser casualidad. */
const MIN_TEMAS = 2

/**
 * Vetas: canales de los que ya venís guardando.
 *
 * Son curadores humanos que hicieron el digging antes que vos, y su catálogo
 * entero está sobre tu tesis. Minar uno cuesta 1 unidad de quota cada 50 videos,
 * contra las 100 que cuesta UNA búsqueda.
 */
export function Vetas() {
  const { affinity, mine, loading } = useCrate()

  const vetas = Object.entries(affinity.channels ?? {})
    .map(([clave, n]) => {
      const [channelId, nombre] = clave.split('|')
      return { channelId, nombre: nombre || channelId, n }
    })
    .filter((v) => v.n >= MIN_TEMAS && v.channelId.startsWith('UC'))
    .sort((a, b) => b.n - a.n)
    .slice(0, 8)

  if (vetas.length === 0) return null

  return (
    <div className="rounded-xl border border-crate-line bg-crate-panel p-4">
      <p className="eyebrow">vetas</p>
      <p className="mt-1 text-sm text-crate-soft">
        Canales de los que ya guardaste. Minarlos trae su catálogo entero, y sale mucho más
        barato que buscar.
      </p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {vetas.map((v) => (
          <button
            key={v.channelId}
            disabled={loading}
            onClick={() => void mine(v.channelId, v.nombre)}
            className="chip hover:border-crate-amber disabled:opacity-50"
            title={`Minar los uploads de ${v.nombre}`}
          >
            ⛏ {v.nombre} <span className="text-crate-faint">{v.n}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
