import { useEffect } from 'react'
import type { EnrichedTrack } from '@/core/entities'
import type { Provenanced } from '@/core/provenance'
import { provenanceLabel } from '@/core/provenance'
import { useCrate } from '@/state/useCrateStore'
import { formatDuration } from '../format'

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
  children,
}: {
  label: string
  value: string
  prov?: Provenanced<unknown>
  wide?: boolean
  children?: React.ReactNode
}) {
  const pct = prov ? Math.round(prov.confidence * 100) : 0
  const vacio = value === '—'
  return (
    <div className={`flex min-w-0 flex-col gap-0.5 ${wide ? 'flex-1' : 'flex-none'}`}>
      <span className="text-[9px] uppercase tracking-[0.18em] text-crate-lcdInk/55">{label}</span>
      <span className="flex items-center gap-1.5">
        <span
          className={`truncate text-[17px] font-bold leading-none ${
            vacio ? 'text-crate-lcdInk/35' : ''
          }`}
        >
          {value}
        </span>
        {children}
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

/** Botoncito de la consola: ÷2 / ×2 / una alternativa. */
function Tecla({
  onClick,
  title,
  children,
  on,
}: {
  onClick: () => void
  title: string
  children: React.ReactNode
  on?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-pressed={on}
      className={`rounded border px-1.5 py-0.5 font-mono text-[10px] font-bold leading-none tracking-wider transition-colors ${
        on
          ? 'border-crate-lcdInk bg-crate-lcdInk/15 text-crate-lcdInk'
          : 'border-crate-lcdInk/35 text-crate-lcdInk/80 hover:border-crate-lcdInk hover:bg-crate-lcdInk/10'
      }`}
    >
      {children}
    </button>
  )
}

/**
 * Readout tipo LCD del análisis de audio (Capa 2, opt-in).
 *
 * Muestra el BPM elegido con su provenance (analizado / plegado a tu rango /
 * tuyo), y cuando hay evidencia del backend, la ventana que se escuchó, si el
 * tempo es ambiguo, y las alternativas de octava. El botón ÷2 / ×2 guarda la
 * corrección con provenance `user/manual`: es el dato que recalibra el prior
 * de tempo contra el oído real, no contra el de un agente.
 */
export function AnalyzePanel({ track, analyzing, onAnalyze }: Props) {
  const { backend, backendChecked, analyses, loadAnalysis, setBpm, checkBackend } = useCrate()
  const bpm = track.bpm
  const deAudio = bpm?.source === 'audio_analysis'
  const corregido = bpm?.source === 'user' && bpm.method === 'manual'
  const isAnalyzed = deAudio || corregido || track.key?.method === 'analyzed'
  const hayMood = Boolean(track.mood)

  // la evidencia (crudo, alternativas, ventana) vive aparte de la ficha
  const analysis = analyses[track.crateId]
  useEffect(() => {
    if (isAnalyzed && !(track.crateId in analyses)) void loadAnalysis(track.crateId)
  }, [isAnalyzed, track.crateId, analyses, loadAnalysis])

  const valor = bpm ? Math.round(bpm.value) : undefined
  const ventana = analysis?.window
  const alternativas = (analysis?.alternatives ?? [])
    .filter((a) => bpm == null || Math.abs(a.value - bpm.value) >= 1)
    .slice(0, 4)

  // sin backend no hay DSP: el botón lo dice en vez de fallar a los 30 s
  const sinBackend = backendChecked && backend === null
  const sinToolchain = Boolean(backend && !backend.ok)
  const bloqueo = sinBackend
    ? 'El backend no responde: levantalo con uvicorn (ver README) para analizar audio. Tocá para volver a probar.'
    : sinToolchain
      ? `El backend no puede bajar audio:\n${backend?.tools.problems.join('\n') ?? ''}\nTocá para volver a mirar.`
      : undefined

  // con el backend caído el botón no se apaga del todo: vuelve a preguntar
  // (/health?refresh=1) y, si ahora está, analiza. Así no hay que recargar.
  const reintentar = async (): Promise<void> => {
    await checkBackend(true)
    if (useCrate.getState().backend?.ok) onAnalyze()
  }

  return (
    <div className={`lcd px-3 py-2 ${analyzing ? 'animate-flicker' : ''}`}>
      <div className="flex items-start gap-4">
        <Readout label="BPM" value={valor != null ? String(valor) : '—'} prov={bpm}>
          {bpm && (deAudio || corregido) && (
            <span className="flex items-center gap-1" role="group" aria-label="Corregir la octava">
              <Tecla
                onClick={() => void setBpm(track, bpm.value / 2)}
                title={`Es la mitad: ${Math.round(bpm.value / 2)} BPM (se guarda como tuyo)`}
              >
                ÷2
              </Tecla>
              <Tecla
                onClick={() => void setBpm(track, bpm.value * 2)}
                title={`Es el doble: ${Math.round(bpm.value * 2)} BPM (se guarda como tuyo)`}
              >
                ×2
              </Tecla>
            </span>
          )}
        </Readout>
        <Readout label="Key" value={track.key ? track.key.value : '—'} prov={track.key} />
        {hayMood && (
          <div className="hidden min-w-0 flex-1 sm:block">
            <Readout label="Mood" value={moodValue(track)} prov={track.mood} wide />
          </div>
        )}

        <div className="ml-auto flex flex-none items-center self-center">
          {isAnalyzed ? (
            <span className="flex items-center gap-1.5 text-[9px] uppercase tracking-[0.16em] text-crate-lcdInk/70">
              <span className={`led ${corregido ? 'led-on' : 'led-go'}`} />
              {corregido ? 'corregido' : 'analizado'}
            </span>
          ) : (
            <button
              onClick={bloqueo ? () => void reintentar() : onAnalyze}
              disabled={analyzing}
              title={
                bloqueo ??
                'Baja el audio a un temporal, recorta 45 s desde el minuto 1, calcula BPM/key y lo borra. Es el último recurso, no el primero.'
              }
              className={`rounded border px-2.5 py-1.5 font-mono text-[10px] font-bold uppercase tracking-[0.12em] transition-colors disabled:cursor-wait disabled:opacity-60 ${
                bloqueo
                  ? 'border-crate-warn/50 text-crate-warn hover:border-crate-warn hover:bg-crate-warn/10'
                  : 'border-crate-lcdInk/40 text-crate-lcdInk hover:border-crate-lcdInk hover:bg-crate-lcdInk/10'
              }`}
            >
              {analyzing ? 'analizando…' : bloqueo ? '🧠 sin backend' : '🧠 analizar'}
            </button>
          )}
        </div>
      </div>

      {/* el cabezal barriendo mientras el backend escucha el fragmento */}
      {analyzing && <div className="scanbar mt-2" />}

      {/* evidencia del DSP: qué se escuchó, cuán seguro está, qué otras octavas vio */}
      {!analyzing && analysis && (deAudio || corregido) && (
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 border-t border-crate-lcdInk/15 pt-2 text-[9px] uppercase tracking-[0.14em] text-crate-lcdInk/60">
          {ventana && (
            <span title="La ventana del track que se analizó">
              ventana {formatDuration(ventana.start_sec) ?? '0:00'}–
              {formatDuration(ventana.start_sec + ventana.seconds) ?? ''}
            </span>
          )}
          {analysis.bpmRaw && analysis.folded && (
            <span title={analysis.reason ?? 'plegado a tu rango'}>
              el DSP leyó {Math.round(analysis.bpmRaw.value)}
            </span>
          )}
          {analysis.ambiguous && (
            <span
              className="flex items-center gap-1 text-crate-warn"
              title="Los dos mejores candidatos de tempo están cerca: mirá las alternativas y corregí si hace falta"
            >
              <span className="led bg-crate-warn" />
              ambiguo
            </span>
          )}
          {alternativas.length > 0 && (
            <span className="flex items-center gap-1" role="group" aria-label="Otras lecturas de tempo">
              <span>o</span>
              {alternativas.map((a) => (
                <Tecla
                  key={a.value}
                  onClick={() => void setBpm(track, a.value)}
                  title={`Candidato con ${Math.round(a.support * 100)}% de evidencia de audio. Elegirlo lo guarda como tuyo.`}
                >
                  {Math.round(a.value)}
                </Tecla>
              ))}
            </span>
          )}
          {analysis.prior && analysis.folded && (
            <span className="ml-auto" title="El rango de tempo de tu crate, con el que se eligió la octava">
              tu rango {analysis.prior.min}–{analysis.prior.max}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
