/**
 * Provenance — cada dato sabe de dónde viene y con qué confianza.
 * Regla de oro de CRATE: nunca mezclar metadata confirmada con inferida/analizada.
 * Ver docs/ENTITY_MODEL.md
 */

export type MetaSource =
  | 'youtube_title'
  | 'youtube_tags'
  | 'youtube_description'
  | 'discogs'
  | 'musicbrainz'
  | 'archive'
  | 'audio_analysis'
  | 'acoustid'
  | 'inferred'
  | 'user'

export type MetaMethod = 'parsed' | 'catalog' | 'analyzed' | 'fingerprint' | 'inferred' | 'manual'

export interface Provenanced<T> {
  value: T
  source: MetaSource
  method: MetaMethod
  /** 0..1 */
  confidence: number
  /** ISO timestamp */
  updatedAt: string
}

const now = (): string => new Date().toISOString()

export function prov<T>(
  value: T,
  source: MetaSource,
  method: MetaMethod,
  confidence: number,
): Provenanced<T> {
  return { value, source, method, confidence: clampConfidence(confidence), updatedAt: now() }
}

/** Dato de catálogo o texto tomado como confirmado (confidence alta). */
export function confirmed<T>(value: T, source: MetaSource, confidence = 1): Provenanced<T> {
  const method: MetaMethod = source === 'discogs' || source === 'musicbrainz' ? 'catalog' : 'parsed'
  return prov(value, source, method, confidence)
}

/** Dato salido del análisis de audio (Capa 2). */
export function analyzed<T>(value: T, confidence: number): Provenanced<T> {
  return prov(value, 'audio_analysis', 'analyzed', confidence)
}

/** Identificación por huella acústica (AcoustID). No depende del texto. */
export function fingerprinted<T>(value: T, confidence: number): Provenanced<T> {
  return prov(value, 'acoustid', 'fingerprint', confidence)
}

/** Dato deducido (ej. mood a partir de género + tags). */
export function inferred<T>(value: T, confidence: number): Provenanced<T> {
  return prov(value, 'inferred', 'inferred', confidence)
}

/** Dato corregido/etiquetado a mano por el usuario. */
export function userSet<T>(value: T): Provenanced<T> {
  return prov(value, 'user', 'manual', 1)
}

/** Etiqueta corta para la UI: "del título" / "analizado 94%" / "inferido 62%". */
export function provenanceLabel(p: Provenanced<unknown>): string {
  const pct = Math.round(p.confidence * 100)
  switch (p.method) {
    case 'catalog':
      return `de ${p.source === 'discogs' ? 'Discogs' : 'MusicBrainz'}`
    case 'parsed':
      return p.source === 'youtube_description'
        ? 'de la descripción'
        : p.source === 'youtube_tags'
          ? 'de los tags'
          : 'del título'
    case 'analyzed':
      return `analizado ${pct}%`
    case 'fingerprint':
      return `huella ${pct}%`
    case 'inferred':
      return `inferido ${pct}%`
    case 'manual':
      return 'tuyo'
  }
}

function clampConfidence(c: number): number {
  return Math.max(0, Math.min(1, c))
}
