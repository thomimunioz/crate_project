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
