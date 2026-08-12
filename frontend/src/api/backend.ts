/**
 * Cliente del backend FastAPI: proxy (CORS/scraping) + analyze (DSP opt-in).
 * En dev, VITE_API_BASE = /api y Vite lo proxea a http://localhost:8787.
 */
const API_BASE = import.meta.env.VITE_API_BASE || '/api'

/** GET a través del proxy con allowlist (para fuentes que CORS bloquea). */
export async function proxyGet<T = any>(url: string): Promise<T> {
  const res = await fetch(`${API_BASE}/proxy?url=${encodeURIComponent(url)}`)
  if (!res.ok) throw new Error(`proxy ${res.status} para ${url}`)
  return res.json() as Promise<T>
}

export interface Confidenced<T> {
  value: T
  confidence: number
}

export interface AnalyzeResult {
  bpm?: Confidenced<number>
  key?: Confidenced<string>
  mood?: Confidenced<{ feels: string[]; textures: string[] }>
  instruments?: Confidenced<string[]>
}

/** Dispara el análisis de audio (Capa 2, opt-in). El backend baja un fragmento y corre DSP. */
export async function analyzeAudio(
  url: string,
  opts?: { startSec?: number; seconds?: number },
): Promise<AnalyzeResult> {
  const res = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, start_sec: opts?.startSec, seconds: opts?.seconds }),
  })
  if (!res.ok) throw new Error(`analyze ${res.status}`)
  return res.json() as Promise<AnalyzeResult>
}

export interface IdentifyCandidate {
  acoustid: string
  /** similitud de huella que devuelve AcoustID (0..1) */
  score: number
  /** score ajustado por cuánto audio se pudo huellar */
  confidence: number
  recording_mbid?: string | null
  artist?: string | null
  title?: string | null
  /** álbumes donde aparece la grabación */
  releases: string[]
  duration_sec?: number | null
}

export interface IdentifyResult {
  candidates: IdentifyCandidate[]
  fingerprint_seconds: number
  lookup_duration_sec: number
}

/**
 * Identifica un track por HUELLA ACÚSTICA (Capa 2, opt-in).
 *
 * Es el desempate cuando el texto no alcanza: títulos en kanji o cirílico,
 * títulos sueltos de una palabra, rips sin descripción. No lee el título.
 */
export async function identifyAudio(url: string): Promise<IdentifyResult> {
  const res = await fetch(`${API_BASE}/identify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
  if (!res.ok) {
    const detalle = await res.json().catch(() => null)
    throw new Error(detalle?.detail ?? `identify ${res.status}`)
  }
  return res.json() as Promise<IdentifyResult>
}
