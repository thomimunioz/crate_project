import { useState } from 'react'
import type { EnrichedTrack } from '@/core/entities'
import { scoreLabel } from '@/core/score'
import { useCrate } from '@/state/useCrateStore'
import { AnalyzePanel } from './AnalyzePanel'

interface Props {
  track: EnrichedTrack
}

export function ResultCard({ track }: Props) {
  const { save, remove, reject, analyze, analyzing, identify, identifying } = useCrate()
  const [showWhy, setShowWhy] = useState(false)
  const [preview, setPreview] = useState(false)

  const e = track.entity
  const score = track.score
  const reasons = score?.reasons ?? []
  const yt = track.sources.find((s) => s.kind === 'youtube')
  const instruments = track.instruments?.value ?? []
  const inCrate = track.status === 'saved' || track.status === 'analyzed'
  const tags = track.tags ?? []
  const pending = track.pending === true

  return (
    <article
      className={`rounded-xl border bg-crate-panel p-4 shadow-lg transition-opacity ${
        pending ? 'border-crate-line/50 opacity-60' : 'border-crate-line'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            {pending ? (
              <span className="eyebrow animate-pulse text-crate-amber">cruzando catálogo…</span>
            ) : score ? (
              <>
                <span className="font-mono text-sm font-bold text-crate-amber">
                  {scoreLabel(score.total)}
                </span>
                <span className="font-mono text-sm text-crate-soft">— {score.total}</span>
              </>
            ) : (
              <span className="eyebrow">en tu crate</span>
            )}
            {!e.confirmed && (
              <span className="chip text-crate-faint" title="No confirmado contra catálogo">
                sin confirmar
              </span>
            )}
          </div>
          <h3 className="mt-1 truncate text-lg font-semibold">
            {e.artist} <span className="text-crate-soft">— {e.title}</span>
          </h3>
          <p className="text-sm text-crate-faint">
            {[e.year, ...e.genres, ...e.styles].filter(Boolean).join(' · ') || 'sin metadata de catálogo'}
            {e.country ? ` · ${e.country}` : ''}
            {e.label ? ` · ${e.label}` : ''}
          </p>
        </div>
        <div className="flex flex-none gap-1">
          {pending ? null : inCrate ? (
            <button
              onClick={() => void remove(track)}
              className="chip border-crate-go text-crate-go"
              title="Sacar del crate"
            >
              ♥
            </button>
          ) : (
            <button
              onClick={() => void save(track)}
              className="chip hover:border-crate-go"
              title="Guardar en tu crate"
            >
              ♡
            </button>
          )}
          {!pending && (
            <button
              onClick={() => void reject(track)}
              className="chip hover:border-crate-stop"
              title="No me interesa"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {(instruments.length > 0 || tags.length > 0) && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {instruments.map((i) => (
            <span key={i} className="chip text-crate-teal">
              {i}
            </span>
          ))}
          {tags.map((t) => (
            <span key={t} className="chip border-crate-amber/40 text-crate-amber" title="tag tuyo">
              #{t}
            </span>
          ))}
        </div>
      )}

      {!pending && !e.confirmed && (
        <button
          onClick={() => void identify(track)}
          disabled={identifying === track.crateId}
          className="chip mt-3 hover:border-crate-teal disabled:opacity-50"
          title="Identificar por huella acústica: no depende del título"
        >
          {identifying === track.crateId ? '🎧 escuchando…' : '🎧 identificar por sonido'}
        </button>
      )}

      {!pending && (
        <div className="mt-3">
          <AnalyzePanel
            track={track}
            analyzing={analyzing === track.crateId}
            onAnalyze={() => void analyze(track)}
          />
        </div>
      )}

      {reasons.length > 0 && (
        <div className="mt-3">
          <button onClick={() => setShowWhy((v) => !v)} className="eyebrow hover:text-crate-amber">
            {showWhy ? '− why this?' : '+ why this?'}
          </button>
          {showWhy && (
            <ul className="mt-2 space-y-1 text-sm text-crate-soft">
              {reasons.map((r, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-crate-amber">•</span>
                  {r}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="mt-3 flex items-center gap-3">
        {yt && (
          <button onClick={() => setPreview((v) => !v)} className="chip hover:border-crate-amber">
            {preview ? '▮ ocultar' : '▶ preview'}
          </button>
        )}
        {track.sources.map((s) => (
          <a
            key={s.id}
            href={s.url}
            target="_blank"
            rel="noreferrer"
            className="eyebrow hover:text-crate-amber"
          >
            {s.kind} ↗
          </a>
        ))}
      </div>

      {preview && yt && (
        <div className="mt-3 aspect-video w-full overflow-hidden rounded-md">
          <iframe
            title={`preview-${track.crateId}`}
            src={`https://www.youtube.com/embed/${yt.nativeId}`}
            className="h-full w-full"
            allow="encrypted-media"
            allowFullScreen
          />
        </div>
      )}
    </article>
  )
}
