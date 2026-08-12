import { useState } from 'react'
import type { SearchQuery } from '@/core/entities'
import { FEELS, TEXTURES } from '@/core/taxonomy'
import type { Feel, Texture } from '@/core/taxonomy'
import { useCrate } from '@/state/useCrateStore'

/** Notas para el selector de key. El modo va aparte, como en la ficha de un disco. */
const NOTAS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'] as const

/**
 * Vetas de arranque: los casos de prueba de F1. Sirven de ejemplo y de atajo
 * cuando abrís la app y no sabés por dónde empezar a cavar.
 */
const ATAJOS = [
  '80s quiet storm',
  'japanese city pop 1982',
  '70s brazilian MPB rhodes melancholic',
  'soul jazz rhodes 75-90 bpm minor',
  'library music cinematic strings 1974',
]

/** Campo de la consola: etiqueta chiquita arriba, control abajo. */
function Campo({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="eyebrow">{label}</span>
      {children}
    </label>
  )
}

/** Filtros estructurados. Diseñado para que a futuro entre lenguaje natural (ver docs/TAXONOMY.md). */
export function FilterBar() {
  const { query, patchQuery, search, loading, results, hideSeen, toggleHideSeen } = useCrate()
  const [advanced, setAdvanced] = useState(false)
  // los rangos se editan de a un extremo: hace falta estado local para no perder el otro
  const [bpmLo, setBpmLo] = useState('')
  const [bpmHi, setBpmHi] = useState('')
  const [yearLo, setYearLo] = useState('')
  const [yearHi, setYearHi] = useState('')
  const [generos, setGeneros] = useState('')
  const [instrumentos, setInstrumentos] = useState('')

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    void search()
  }

  const setList = (key: 'genres' | 'instruments', raw: string) =>
    patchQuery({ [key]: raw ? raw.split(',').map((s) => s.trim()).filter(Boolean) : undefined })

  const setRange = (key: 'bpm' | 'year', lo: string, hi: string) => {
    if (!lo && !hi) return patchQuery({ [key]: undefined })
    patchQuery({ [key]: [Number(lo) || 0, Number(hi) || 9999] })
  }

  /** Toggle sobre una lista cerrada de la taxonomía (feel / texture). */
  const toggleMood = <K extends 'feels' | 'textures'>(key: K, valor: Feel | Texture) => {
    const actuales = (query[key] ?? []) as string[]
    const proximos = actuales.includes(valor)
      ? actuales.filter((v) => v !== valor)
      : [...actuales, valor]
    patchQuery({ [key]: proximos.length ? proximos : undefined } as Partial<SearchQuery>)
  }

  const atajo = (texto: string) => {
    patchQuery({ text: texto })
    void search()
  }

  // resumen de lo que está filtrando ahora mismo, con su forma de apagarlo
  const activos: Array<{ label: string; clear: () => void }> = []
  if (query.genres?.length)
    activos.push({
      label: query.genres.join(' + '),
      clear: () => {
        setGeneros('')
        patchQuery({ genres: undefined })
      },
    })
  if (query.instruments?.length)
    activos.push({
      label: query.instruments.join(' + '),
      clear: () => {
        setInstrumentos('')
        patchQuery({ instruments: undefined })
      },
    })
  if (query.bpm)
    activos.push({
      label: `${query.bpm[0]}–${query.bpm[1]} bpm`,
      clear: () => {
        setBpmLo('')
        setBpmHi('')
        patchQuery({ bpm: undefined })
      },
    })
  if (query.year)
    activos.push({
      label: `${query.year[0]}–${query.year[1]}`,
      clear: () => {
        setYearLo('')
        setYearHi('')
        patchQuery({ year: undefined })
      },
    })
  if (query.key)
    activos.push({ label: `${query.key}${query.mode === 'minor' ? 'm' : ''}`, clear: () => patchQuery({ key: undefined }) })
  for (const f of query.feels ?? [])
    activos.push({ label: f, clear: () => toggleMood('feels', f) })
  for (const t of query.textures ?? [])
    activos.push({ label: t, clear: () => toggleMood('textures', t) })
  if (query.energy)
    activos.push({ label: `energía ${query.energy[0]}`, clear: () => patchQuery({ energy: undefined }) })

  return (
    <form onSubmit={onSubmit} className="panel p-3 sm:p-4">
      <div className="flex items-center gap-2">
        <span className="tape">buscar</span>
        <span className="eyebrow hidden text-crate-dust sm:inline">
          the internet is the crate
        </span>
      </div>

      <div className="mt-3 flex gap-2">
        <div className="relative flex-1">
          <input
            value={query.text}
            onChange={(e) => patchQuery({ text: e.target.value })}
            placeholder="soul jazz rhodes 75-90 bpm minor…"
            aria-label="Qué estás buscando"
            className="field py-3 pl-9 font-mono text-sm"
          />
          <span
            aria-hidden
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-crate-dust"
          >
            ⌕
          </span>
        </div>
        <button type="submit" disabled={loading} className="btn btn-amber px-5 text-xs">
          {loading ? '···' : 'DIG'}
        </button>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2">
        <button
          type="button"
          onClick={() => setAdvanced((v) => !v)}
          aria-expanded={advanced}
          className="eyebrow transition-colors hover:text-crate-amber"
        >
          {advanced ? '− filtros' : '+ filtros'}
        </button>

        {activos.map((a, i) => (
          <button
            key={`${a.label}-${i}`}
            type="button"
            onClick={a.clear}
            className="chip-btn chip-on"
            title="Sacar este filtro"
          >
            {a.label} <span aria-hidden>✕</span>
          </button>
        ))}

        {/* "no me muestres lo que ya vi" es un filtro más: vive acá, siempre a mano */}
        <button
          type="button"
          onClick={toggleHideSeen}
          aria-pressed={hideSeen}
          className={`chip-btn ml-auto ${hideSeen ? 'chip-on' : 'text-crate-soft'}`}
          title="No mostrar lo que ya viste en búsquedas anteriores"
        >
          {hideSeen ? '🙈 ocultando vistos' : '👁 mostrando todo'}
        </button>
      </div>

      {advanced && (
        <div className="perf mt-3 grid grid-cols-2 gap-3 pt-3 sm:grid-cols-4">
          <Campo label="géneros">
            <input
              value={generos}
              onChange={(e) => {
                setGeneros(e.target.value)
                setList('genres', e.target.value)
              }}
              placeholder="Soul, MPB"
              className="field py-1.5 text-xs"
            />
          </Campo>

          <Campo label="instrumentos">
            <input
              value={instrumentos}
              onChange={(e) => {
                setInstrumentos(e.target.value)
                setList('instruments', e.target.value)
              }}
              placeholder="Rhodes, strings"
              className="field py-1.5 text-xs"
            />
          </Campo>

          <Campo label="bpm">
            <div className="flex items-center gap-1">
              <input
                type="number"
                inputMode="numeric"
                value={bpmLo}
                placeholder="70"
                aria-label="BPM mínimo"
                className="field py-1.5 text-center font-mono text-xs"
                onChange={(e) => {
                  setBpmLo(e.target.value)
                  setRange('bpm', e.target.value, bpmHi)
                }}
              />
              <span aria-hidden className="text-crate-dust">
                –
              </span>
              <input
                type="number"
                inputMode="numeric"
                value={bpmHi}
                placeholder="90"
                aria-label="BPM máximo"
                className="field py-1.5 text-center font-mono text-xs"
                onChange={(e) => {
                  setBpmHi(e.target.value)
                  setRange('bpm', bpmLo, e.target.value)
                }}
              />
            </div>
          </Campo>

          <Campo label="años">
            <div className="flex items-center gap-1">
              <input
                type="number"
                inputMode="numeric"
                value={yearLo}
                placeholder="1970"
                aria-label="Año desde"
                className="field py-1.5 text-center font-mono text-xs"
                onChange={(e) => {
                  setYearLo(e.target.value)
                  setRange('year', e.target.value, yearHi)
                }}
              />
              <span aria-hidden className="text-crate-dust">
                –
              </span>
              <input
                type="number"
                inputMode="numeric"
                value={yearHi}
                placeholder="1979"
                aria-label="Año hasta"
                className="field py-1.5 text-center font-mono text-xs"
                onChange={(e) => {
                  setYearHi(e.target.value)
                  setRange('year', yearLo, e.target.value)
                }}
              />
            </div>
          </Campo>

          <Campo label="key">
            <select
              value={query.key ?? ''}
              onChange={(e) => patchQuery({ key: e.target.value || undefined })}
              className="field py-1.5 font-mono text-xs"
            >
              <option value="">cualquiera</option>
              {NOTAS.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </Campo>

          <Campo label="modo">
            <select
              value={query.mode ?? ''}
              onChange={(e) =>
                patchQuery({ mode: (e.target.value || undefined) as SearchQuery['mode'] })
              }
              className="field py-1.5 font-mono text-xs"
            >
              <option value="">cualquiera</option>
              <option value="minor">minor</option>
              <option value="major">major</option>
            </select>
          </Campo>

          <Campo label="energía">
            <div className="flex items-center gap-1.5 pt-1">
              {[1, 2, 3, 4, 5].map((n) => {
                const on = query.energy?.[0] === n
                return (
                  <button
                    key={n}
                    type="button"
                    aria-pressed={on}
                    aria-label={`energía ${n}`}
                    onClick={() =>
                      patchQuery({ energy: on ? undefined : [n, n] })
                    }
                    className={`h-6 flex-1 rounded-sm border transition-colors ${
                      on
                        ? 'border-crate-amber bg-crate-amber'
                        : 'border-crate-line bg-crate-bg hover:border-crate-soft'
                    }`}
                  />
                )
              })}
            </div>
          </Campo>

          {/* mood: taxonomía cerrada, nada de campo libre (ver docs/TAXONOMY.md) */}
          <div className="col-span-2 flex flex-col gap-1.5 sm:col-span-4">
            <span className="eyebrow">
              mood <span className="text-crate-faint">· viaja en la query, todavía no pesa en el score</span>
            </span>
            <div className="flex flex-wrap gap-1.5">
              {FEELS.map((f) => (
                <button
                  key={f}
                  type="button"
                  aria-pressed={query.feels?.includes(f) ?? false}
                  onClick={() => toggleMood('feels', f)}
                  className={`chip-btn ${query.feels?.includes(f) ? 'chip-on' : 'text-crate-soft'}`}
                >
                  {f}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {TEXTURES.map((t) => (
                <button
                  key={t}
                  type="button"
                  aria-pressed={query.textures?.includes(t) ?? false}
                  onClick={() => toggleMood('textures', t)}
                  className={`chip-btn ${
                    query.textures?.includes(t) ? 'chip-on' : 'text-crate-teal/80'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* atajos: solo cuando la pantalla está vacía, para no estorbar mientras diggeás */}
      {results.length === 0 && !loading && (
        <div className="perf mt-3 flex flex-wrap items-center gap-1.5 pt-3">
          <span className="eyebrow mr-1">probá</span>
          {ATAJOS.map((a) => (
            <button key={a} type="button" onClick={() => atajo(a)} className="chip-btn font-mono">
              {a}
            </button>
          ))}
        </div>
      )}
    </form>
  )
}
