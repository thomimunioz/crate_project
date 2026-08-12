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
    <section className="panel p-4">
      <div className="flex items-center gap-2">
        <span className="tape">vetas</span>
        <span className="eyebrow">1 unidad cada 50 videos</span>
      </div>
      <p className="mt-2.5 text-sm text-crate-soft">
        Canales de los que ya guardaste: alguien hizo el digging antes que vos. Minarlos trae su
        catálogo entero y sale mucho más barato que buscar.
      </p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {vetas.map((v) => (
          <button
            key={v.channelId}
            disabled={loading}
            onClick={() => void mine(v.channelId, v.nombre)}
            className="chip-btn hover:border-crate-amber hover:text-crate-amber"
            title={`Minar los uploads de ${v.nombre}`}
          >
            <span aria-hidden>⛏</span>
            <span className="max-w-[16ch] truncate">{v.nombre}</span>
            <span className="font-mono text-crate-faint">{v.n}</span>
          </button>
        ))}
      </div>
    </section>
  )
}
