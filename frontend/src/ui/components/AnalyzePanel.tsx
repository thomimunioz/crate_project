import type { EnrichedTrack } from '@/core/entities'
import { provenanceLabel } from '@/core/provenance'

interface Props {
  track: EnrichedTrack
  analyzing: boolean
  onAnalyze: () => void
}

function Readout({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase tracking-wider text-crate-lcdInk/60">{label}</span>
      <span className="text-lg font-bold leading-tight">{value}</span>
      {hint && <span className="text-[10px] text-crate-lcdInk/50">{hint}</span>}
    </div>
  )
}

/** Readout tipo LCD del análisis de audio (Capa 2, opt-in). */
export function AnalyzePanel({ track, analyzing, onAnalyze }: Props) {
  const isAnalyzed = track.bpm?.method === 'analyzed' || track.key?.method === 'analyzed'

  return (
    <div className="lcd flex items-center justify-between gap-4 px-4 py-3">
      <div className="flex gap-6">
        <Readout
          label="BPM"
          value={track.bpm ? String(Math.round(track.bpm.value)) : '—'}
          hint={track.bpm ? provenanceLabel(track.bpm) : 'sin dato'}
        />
        <Readout
          label="Key"
          value={track.key ? track.key.value : '—'}
          hint={track.key ? provenanceLabel(track.key) : 'sin dato'}
        />
      </div>
      {!isAnalyzed && (
        <button
          onClick={onAnalyze}
          disabled={analyzing}
          className="rounded border border-crate-lcdInk/40 px-3 py-1.5 text-xs font-bold text-crate-lcdInk disabled:opacity-50"
        >
          {analyzing ? 'analizando…' : '🧠 Analizar audio'}
        </button>
      )}
    </div>
  )
}
