import { useMemo, useState } from 'react'
import { useCrate } from '@/state/useCrateStore'
import { parseVetaRef, type VetaRef } from '@/sources/youtube'
import { CANALES, type Canal } from '@/core/canales'
import { detectarEscenas } from '@/core/scenes'

/** Una veta se gana con al menos dos temas guardados: uno puede ser casualidad. */
const MIN_TEMAS = 2
/** cuántos chips de cada tipo como máximo: es un atajo, no un directorio */
const MAX_CHIPS = 8

interface Chip {
  veta: VetaRef
  nombre: string
  /** de dónde sale el chip */
  de: 'crate' | 'curador'
  /** temas guardados de ese canal (tu crate) o en el benchmark (curador) */
  n: number
}

/**
 * Vetas: playlists y canales de otros diggers.
 *
 * Lo que funcionó a mano el 19-sep fue cavar playlists AJENAS enteras (1.958
 * temas → 206 sugerencias → 53% guardado). Acá se pega una playlist o un
 * canal y se cava por tandas, sin gastar quota para listar (yt-dlp); lo que
 * sale entra como `seen`, nunca como guardado: la veta es de otro.
 *
 * Abajo, atajos: canales de los que ya guardaste (de tu crate) y curadores
 * validados a mano para la escena que estás buscando (`core/canales.ts`).
 */
export function Vetas() {
  const { affinity, mine, loading, query, mining } = useCrate()
  const [input, setInput] = useState('')
  const [invalido, setInvalido] = useState(false)

  const deCrate: Chip[] = useMemo(
    () =>
      Object.entries(affinity.channels ?? {})
        .map(([clave, n]) => {
          const [channelId, nombre] = clave.split('|')
          return { channelId, nombre: nombre || channelId, n }
        })
        // sin channelId (clave "|uploader") no hay forma de listar el canal: se omite
        .filter((v) => v.n >= MIN_TEMAS && v.channelId.startsWith('UC'))
        .sort((a, b) => b.n - a.n)
        .slice(0, MAX_CHIPS)
        .map((v) => ({
          veta: { kind: 'channel', ref: v.channelId, nombre: v.nombre },
          nombre: v.nombre,
          de: 'crate',
          n: v.n,
        })),
    [affinity.channels],
  )

  // curadores validados para la escena pedida; sin escena, los que más dieron
  const curadores: Chip[] = useMemo(() => {
    const escenas = detectarEscenas(query.text).map((e) => e.id)
    const yaEnCrate = new Set(deCrate.map((c) => c.veta.ref))
    const candidatos: Canal[] = CANALES.filter(
      (c) =>
        c.rol === 'curador' &&
        c.channelId &&
        !yaEnCrate.has(c.channelId) &&
        (escenas.length === 0 || (c.escenas ?? []).some((e) => escenas.includes(e))),
    )
    return candidatos
      .sort((a, b) => (b.guardados ?? 0) - (a.guardados ?? 0))
      .slice(0, MAX_CHIPS)
      .map((c) => ({
        veta: { kind: 'channel', ref: c.channelId as string, nombre: c.nombre },
        nombre: c.nombre,
        de: 'curador',
        n: c.guardados ?? 0,
      }))
  }, [query.text, deCrate])

  const cavar = (e: React.FormEvent) => {
    e.preventDefault()
    const ref = parseVetaRef(input)
    if (!ref) {
      setInvalido(true)
      return
    }
    setInvalido(false)
    setInput('')
    void mine(ref)
  }

  const chip = (c: Chip) => {
    const activa = mining?.id === c.veta.ref
    return (
      <button
        key={`${c.de}:${c.veta.ref}`}
        disabled={loading}
        onClick={() => void mine(c.veta)}
        aria-pressed={activa}
        className={`chip-btn ${activa ? 'chip-on' : 'hover:border-crate-amber hover:text-crate-amber'}`}
        title={
          c.de === 'crate'
            ? `Cavar los uploads de ${c.nombre}: ya guardaste ${c.n} de acá`
            : `Curador validado a mano (${c.n} guardados el 19-sep): cavar sus uploads`
        }
      >
        <span aria-hidden>⛏</span>
        <span className="max-w-[16ch] truncate">{c.nombre}</span>
        {c.n > 0 && <span className="font-mono text-crate-faint">{c.n}</span>}
      </button>
    )
  }

  return (
    <section className="panel p-4">
      <div className="flex items-center gap-2">
        <span className="tape">vetas</span>
        <span className="eyebrow">playlists y canales de otros diggers · 0 quota para listar</span>
      </div>
      <p className="mt-2.5 text-sm text-crate-soft">
        Pegá una playlist o un canal de otro digger y cavalo entero, de a 24. Se lee todo:
        la joya no se anuncia en el título. Lo que salga queda como visto, no como guardado.
      </p>

      <form onSubmit={cavar} className="mt-3 flex gap-2">
        <input
          value={input}
          onChange={(e) => {
            setInput(e.target.value)
            if (invalido) setInvalido(false)
          }}
          disabled={loading}
          aria-label="Playlist o canal de YouTube para cavar"
          aria-invalid={invalido}
          placeholder="https://www.youtube.com/playlist?list=… · @handle · UC…"
          className={`field py-2 font-mono text-xs ${invalido ? 'border-crate-stop' : ''}`}
        />
        <button type="submit" disabled={loading || !input.trim()} className="btn btn-amber px-4 text-xs">
          ⛏ cavar
        </button>
      </form>
      {invalido && (
        <p className="mt-1.5 text-xs text-crate-stop" role="alert">
          No parece una playlist ni un canal de YouTube. Vale una URL con <span className="font-mono">?list=</span>, un
          id <span className="font-mono">PL…</span>/<span className="font-mono">UC…</span> o un{' '}
          <span className="font-mono">@handle</span>. Los mixes <span className="font-mono">RD…</span> no se listan.
        </p>
      )}

      {(deCrate.length > 0 || curadores.length > 0) && (
        <div className="mt-3 flex flex-col gap-2">
          {deCrate.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="eyebrow mr-1" title="Canales de los que ya guardaste: alguien hizo el digging antes que vos">
                de tu crate
              </span>
              {deCrate.map(chip)}
            </div>
          )}
          {curadores.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="eyebrow mr-1" title="Validados a mano el 19-sep-2026; ver core/canales.ts">
                curadores {query.text.trim() ? 'de la escena' : 'validados'}
              </span>
              {curadores.map(chip)}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
