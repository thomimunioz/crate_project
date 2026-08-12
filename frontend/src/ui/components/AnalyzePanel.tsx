import type { EnrichedTrack } from '@/core/entities'
import type { Provenanced } from '@/core/provenance'
import { provenanceLabel } from '@/core/provenance'

interface Props {
  track: EnrichedTrack
  analyzing: boolean
  onAnalyze: () => void
}

/** Un dato del display: valor grande, de dónde salió, y con cuánta confianza. */
function Readout({
  label,
  value,
  prov,
  wide,
}: {
  label: string
  value: string
  prov?: Provenanced<unknown>
  wide?: boolean
}) {
  const pct = prov ? Math.round(prov.confidence * 100) : 0
  const vacio = value === '—'
  return (
    <div className={`flex min-w-0 flex-col gap-0.5 ${wide ? 'flex-1' : 'flex-none'}`}>
      <span className="text-[9px] uppercase tracking-[0.18em] text-crate-lcdInk/55">{label}</span>
      <span
        className={`truncate text-[17px] font-bold leading-none ${
          vacio ? 'text-crate-lcdInk/35' : ''
        }`}
      >
        {value}
      </span>
      {/* provenance: nunca se colapsa con el valor, siempre se ve de dónde sale */}
      <span className="truncate text-[9px] leading-tight text-crate-lcdInk/55">
        {prov ? provenanceLabel(prov) : 'sin dato'}
      </span>
      <span
        className="meter mt-px max-w-[72px] text-crate-lcdInk/70"
        role="img"
        aria-label={prov ? `confianza ${pct}%` : 'sin confianza'}
      >
        <span className="meter-fill" style={{ width: `${pct}%` }} />
      </span>
    </div>
  )
}

/** Mood en una línea: `dusty · melancholic` + energía, si la hay. */
function moodValue(t: EnrichedTrack): string {
  const m = t.mood?.value
  if (!m) return '—'
  const partes = [...m.textures.slice(0, 1), ...m.feels.slice(0, 2)]
  if (partes.length === 0 && m.energy == null) return '—'
  const txt = partes.join(' · ')
  return m.energy != null ? `${txt || 'energía'} ${'▮'.repeat(m.energy)}` : txt
}

/** Readout tipo LCD del análisis de audio (Capa 2, opt-in). */
export function AnalyzePanel({ track, analyzing, onAnalyze }: Props) {
  const isAnalyzed = track.bpm?.method === 'analyzed' || track.key?.method === 'analyzed'
  const hayMood = Boolean(track.mood)

  return (
    <div className={`lcd px-3 py-2 ${analyzing ? 'animate-flicker' : ''}`}>
      <div className="flex items-start gap-4">
        <Readout
          label="BPM"
          value={track.bpm ? String(Math.round(track.bpm.value)) : '—'}
          prov={track.bpm}
        />
        <Readout label="Key" value={track.key ? track.key.value : '—'} prov={track.key} />
        {hayMood && (
          <div className="hidden min-w-0 flex-1 sm:block">
            <Readout label="Mood" value={moodValue(track)} prov={track.mood} wide />
          </div>
        )}

        <div className="ml-auto flex flex-none items-center self-center">
          {isAnalyzed ? (
            <span className="flex items-center gap-1.5 text-[9px] uppercase tracking-[0.16em] text-crate-lcdInk/70">
              <span className="led led-go" />
              analizado
            </span>
          ) : (
            <button
              onClick={onAnalyze}
              disabled={analyzing}
              title="Baja un fragmento y calcula BPM/key con DSP. Es el último recurso, no el primero."
              className="rounded border border-crate-lcdInk/40 px-2.5 py-1.5 font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-crate-lcdInk transition-colors hover:border-crate-lcdInk hover:bg-crate-lcdInk/10 disabled:cursor-wait disabled:opacity-60"
            >
              {analyzing ? 'analizando…' : '🧠 analizar'}
            </button>
          )}
        </div>
      </div>

      {/* el cabezal barriendo mientras el backend escucha el fragmento */}
      {analyzing && <div className="scanbar mt-2" />}
    </div>
  )
}
