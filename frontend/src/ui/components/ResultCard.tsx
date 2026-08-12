import { useEffect, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import type { EnrichedTrack } from '@/core/entities'
import { scoreLabel } from '@/core/score'
import { provenanceLabel } from '@/core/provenance'
import { useCrate } from '@/state/useCrateStore'
import { AnalyzePanel } from './AnalyzePanel'
import { formatCount, formatDuration, formatStamp, scoreTier, splitLabel } from '../format'

interface Props {
  track: EnrichedTrack
}

/**
 * Devuelve true un rato corto cada vez que `condicion` pasa de false a true.
 * Sirve para que la animación sea del CAMBIO y no del montaje: si no, todo el
 * crate se sella de nuevo cada vez que se rearma la lista.
 */
function useDestello(condicion: boolean, ms: number): boolean {
  const previo = useRef(condicion)
  const [activo, setActivo] = useState(false)
  useEffect(() => {
    if (!previo.current && condicion) {
      setActivo(true)
      const id = window.setTimeout(() => setActivo(false), ms)
      previo.current = condicion
      return () => window.clearTimeout(id)
    }
    previo.current = condicion
    return undefined
  }, [condicion, ms])
  return activo
}

/** Tapa: la miniatura de la fuente. Si no hay, un disco dibujado. */
function Tapa({ src, alt, pending }: { src?: string; alt: string; pending: boolean }) {
  return (
    <div className="relative h-16 w-16 flex-none overflow-hidden rounded-md border border-crate-line bg-crate-bg sm:h-[84px] sm:w-[84px]">
      {src ? (
        <img
          src={src}
          alt={alt}
          loading="lazy"
          referrerPolicy="no-referrer"
          className={`tapa ${pending ? 'opacity-70 blur-[1px]' : ''}`}
        />
      ) : (
        // disco sin funda: el fallback también es del mundo del crate
        <div className="grid h-full w-full place-items-center bg-crate-panel2">
          <div className="grid h-9 w-9 place-items-center rounded-full border border-crate-dust bg-crate-bg sm:h-11 sm:w-11">
            <span className="h-2 w-2 rounded-full bg-crate-dust sm:h-2.5 sm:w-2.5" />
          </div>
        </div>
      )}
    </div>
  )
}

/** Sticker de precio con el CRATE Score. Es el dato que se lee primero. */
function Sticker({ total, pending }: { total?: number; pending: boolean }) {
  if (pending || total == null) {
    return (
      <div
        className="absolute -bottom-2 -right-2 grid h-10 w-10 place-items-center rounded-full border border-dashed border-crate-dust bg-crate-panel font-mono text-crate-faint sm:h-11 sm:w-11"
        aria-label="score pendiente"
      >
        <span className="animate-pulse text-sm">··</span>
      </div>
    )
  }
  const tier = scoreTier(total)
  return (
    <div
      className="sticker absolute -bottom-2 -right-2 h-10 w-10 text-[15px] sm:h-11 sm:w-11 sm:text-[17px]"
      style={{ '--sticker-bg': tier.bg, '--sticker-ink': tier.ink } as CSSProperties}
      aria-label={`CRATE score ${total} de 100`}
      title={`CRATE score ${total}/100`}
    >
      {total}
    </div>
  )
}

export function ResultCard({ track }: Props) {
  const { save, remove, reject, analyze, analyzing, identify, identifying } = useCrate()
  const [showWhy, setShowWhy] = useState(false)
  const [preview, setPreview] = useState(false)

  const e = track.entity
  const score = track.score
  const reasons = score?.reasons ?? []
  const yt = track.sources.find((s) => s.kind === 'youtube')
  const src = track.sources[0]
  const instruments = track.instruments?.value ?? []
  const inCrate = track.status === 'saved' || track.status === 'analyzed'
  const tags = track.tags ?? []
  const pending = track.pending === true
  const tier = score ? scoreTier(score.total) : undefined
  const label = score ? splitLabel(scoreLabel(score.total)) : undefined
  // el artista todavía no se resolvió: el placeholder del pipeline lo deja así
  const sinArtista = !e.artist || e.artist === 'Buscando…'

  // la ficha se revela cuando el cruce la completa: pasa de polvo a dato
  const revelando = useDestello(!pending, 700)
  // el sello cae en el momento en que la guardás, no cada vez que se pinta la lista
  const sellando = useDestello(inCrate, 400)

  // ficha: año · géneros · estilos arriba, y abajo las señales de la fuente
  const catalogo = [e.year, ...e.genres, ...e.styles].filter(Boolean).join(' · ')
  const señales = [
    src?.uploader,
    e.label,
    e.country,
    formatDuration(src?.durationSec),
    track.rarity.youtubeViews != null ? `${formatCount(track.rarity.youtubeViews)} views` : null,
    track.rarity.discogsWant != null && track.rarity.discogsHave != null
      ? `${formatCount(track.rarity.discogsWant)} want / ${formatCount(track.rarity.discogsHave)} have`
      : null,
  ].filter(Boolean) as string[]

  return (
    <article
      className="ficha"
      // sin score todavía no hay tier: el canto de la ficha cae al color por defecto
      style={tier ? ({ '--tier': tier.bg } as CSSProperties) : undefined}
      aria-label={`${sinArtista ? '' : `${e.artist} — `}${e.title}`}
    >
      <div className={`group p-3 sm:p-4 ${revelando ? 'animate-reveal' : ''}`}>
        <div className="flex items-start gap-3 sm:gap-4">
          <div className="relative flex-none">
            <Tapa src={src?.thumbnail} alt="" pending={pending} />
            <Sticker total={score?.total} pending={pending} />
          </div>

          <div className="min-w-0 flex-1">
            {/* renglón de estado: tier del score, sellos y confirmación */}
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              {pending ? (
                <span className="eyebrow flex items-center gap-1.5 text-crate-amber">
                  <span className="led led-on animate-pulse" />
                  cruzando catálogo
                </span>
              ) : label ? (
                <span
                  className="font-mono text-[11px] font-bold uppercase tracking-[0.16em]"
                  style={{ color: tier?.bg }}
                >
                  {label.icon && (
                    <span aria-hidden className="mr-1">
                      {label.icon}
                    </span>
                  )}
                  {label.text}
                </span>
              ) : (
                <span className="eyebrow">ficha del crate</span>
              )}

              {inCrate && (
                <span
                  className={`sello ${sellando ? 'animate-stamp' : ''} ${
                    track.status === 'analyzed'
                      ? 'border-crate-amber text-crate-amber'
                      : 'border-crate-go text-crate-go'
                  }`}
                >
                  {track.status === 'analyzed' ? 'analizado' : 'en el crate'}
                </span>
              )}

              {!pending && !e.confirmed && (
                <span
                  className="eyebrow"
                  title="El cruce contra catálogo no superó el umbral: no afirmamos la obra"
                >
                  &#9671; sin confirmar
                </span>
              )}
            </div>

            <h3
              className="mt-1 truncate text-[15px] font-semibold leading-snug sm:text-base"
              title={sinArtista ? e.title : `${e.artist} — ${e.title}`}
            >
              {!sinArtista && <span>{e.artist} </span>}
              <span className={sinArtista ? '' : 'text-crate-soft'}>
                {sinArtista ? e.title : `— ${e.title}`}
              </span>
            </h3>

            {/* datos de catálogo: mientras se cruza, huecos de polvo */}
            {pending ? (
              <div className="mt-1.5 flex items-center gap-2">
                <span className="skel h-2.5 w-24" />
                <span className="skel h-2.5 w-16" />
              </div>
            ) : (
              <p className="mt-1 truncate font-mono text-[11px] text-crate-soft">
                {catalogo || <span className="text-crate-faint">sin metadata de catálogo</span>}
              </p>
            )}

            {señales.length > 0 && (
              <p className="mt-0.5 truncate font-mono text-[10px] text-crate-faint">
                {señales.join('  ·  ')}
              </p>
            )}
          </div>

          {/* acciones: guardar / descartar. Se apagan mientras la ficha se cruza. */}
          {!pending && (
            <div className="flex flex-none flex-col gap-1">
              <button
                onClick={() => void (inCrate ? remove(track) : save(track))}
                aria-pressed={inCrate}
                aria-label={inCrate ? 'Sacar del crate' : 'Guardar en tu crate'}
                title={inCrate ? 'Sacar del crate' : 'Guardar en tu crate'}
                className={`grid h-8 w-8 place-items-center rounded-md border text-sm transition-colors ${
                  inCrate
                    ? 'border-crate-go bg-crate-go/10 text-crate-go'
                    : 'border-crate-line text-crate-soft hover:border-crate-go hover:text-crate-go'
                }`}
              >
                {inCrate ? '♥' : '♡'}
              </button>
              <button
                onClick={() => void reject(track)}
                aria-label="No me interesa: no volver a mostrarlo"
                title="No me interesa: no volver a mostrarlo"
                className="grid h-8 w-8 place-items-center rounded-md border border-crate-line text-sm text-crate-soft transition-colors hover:border-crate-stop hover:text-crate-stop"
              >
                ✕
              </button>
            </div>
          )}
        </div>

        {/* etiquetas: instrumentos del catálogo + tus tags */}
        {pending ? (
          <div className="mt-3 flex gap-1.5">
            <span className="skel h-6 w-16 rounded-md" />
            <span className="skel h-6 w-12 rounded-md" />
          </div>
        ) : (
          (instruments.length > 0 || tags.length > 0) && (
            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              {instruments.map((i) => (
                <span key={i} className="chip border-crate-teal/35 text-crate-teal">
                  {i}
                </span>
              ))}
              {tags.map((t) => (
                <span
                  key={t}
                  className="chip border-crate-amber/40 text-crate-amber"
                  title="etiqueta tuya"
                >
                  #{t}
                </span>
              ))}
              {/* provenance de los instrumentos: nunca se muestra el dato pelado */}
              {track.instruments && (
                <span className="eyebrow">
                  {provenanceLabel(track.instruments)}
                </span>
              )}
            </div>
          )
        )}

        {/* consola de datos */}
        <div className="mt-3">
          {pending ? (
            <div className="lcd px-3 py-2 opacity-70">
              <div className="flex items-end gap-4">
                <div className="flex flex-col gap-0.5">
                  <span className="text-[9px] uppercase tracking-[0.18em] text-crate-lcdInk/55">
                    BPM
                  </span>
                  <span className="text-[17px] font-bold leading-none text-crate-lcdInk/35">—</span>
                </div>
                <div className="flex flex-col gap-0.5">
                  <span className="text-[9px] uppercase tracking-[0.18em] text-crate-lcdInk/55">
                    Key
                  </span>
                  <span className="text-[17px] font-bold leading-none text-crate-lcdInk/35">—</span>
                </div>
                <span className="ml-auto self-center text-[9px] uppercase tracking-[0.16em] text-crate-lcdInk/50">
                  leyendo ficha…
                </span>
              </div>
              <div className="scanbar mt-2" />
            </div>
          ) : (
            <AnalyzePanel
              track={track}
              analyzing={analyzing === track.crateId}
              onAnalyze={() => void analyze(track)}
            />
          )}
        </div>

        {/* why this: el score nunca es un numerito mágico */}
        {reasons.length > 0 && (
          <div className="mt-3">
            <button
              onClick={() => setShowWhy((v) => !v)}
              aria-expanded={showWhy}
              className="eyebrow transition-colors hover:text-crate-amber"
            >
              {showWhy ? '− why this?' : '+ why this?'}
            </button>
            {showWhy && (
              <ul className="perf mt-2 space-y-1 pt-2 text-[13px] leading-snug text-crate-soft">
                {reasons.map((r, i) => (
                  <li key={i} className="flex gap-2">
                    <span aria-hidden className="text-crate-amber">
                      •
                    </span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* pie de la ficha: preview, fuentes, identificación y sello de fecha */}
        {!pending && (
          <div className="perf mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 pt-3">
            {yt && (
              <button
                onClick={() => setPreview((v) => !v)}
                aria-expanded={preview}
                className="chip-btn hover:border-crate-amber hover:text-crate-amber"
              >
                {preview ? '▮ ocultar' : '▶ preview'}
              </button>
            )}

            {!e.confirmed && (
              <button
                onClick={() => void identify(track)}
                disabled={identifying === track.crateId}
                className="chip-btn hover:border-crate-teal hover:text-crate-teal"
                title="Identificar por huella acústica: no depende del título"
              >
                {identifying === track.crateId ? '🎧 escuchando…' : '🎧 identificar'}
              </button>
            )}

            <div className="ml-auto flex items-center gap-3">
              {track.sources.map((s) => (
                <a
                  key={s.id}
                  href={s.url}
                  target="_blank"
                  rel="noreferrer"
                  className="eyebrow transition-colors hover:text-crate-amber"
                >
                  {s.kind} ↗
                </a>
              ))}
              {/* timestamp: cuándo cayó esta ficha en tu crate */}
              <span
                className="font-mono text-[10px] tracking-wider text-crate-faint"
                title={`visto por primera vez: ${track.firstSeenAt}`}
              >
                {formatStamp(track.firstSeenAt)}
              </span>
            </div>
          </div>
        )}

        {preview && yt && (
          <div className="mt-3 overflow-hidden rounded-md border border-crate-line bg-crate-lcd">
            <div className="flex items-center gap-2 border-b border-crate-line px-2 py-1">
              <span className="led led-on" />
              <span className="eyebrow text-crate-lcdInk/70">preview · youtube</span>
            </div>
            <div className="aspect-video w-full">
              <iframe
                title={`preview-${track.crateId}`}
                src={`https://www.youtube.com/embed/${yt.nativeId}`}
                className="h-full w-full"
                loading="lazy"
                allow="encrypted-media"
                allowFullScreen
              />
            </div>
          </div>
        )}
      </div>
    </article>
  )
}
