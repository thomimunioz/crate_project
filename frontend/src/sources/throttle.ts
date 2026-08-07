/**
 * Rate limiting por fuente.
 *
 * El pipeline enriquece candidatos en paralelo, pero las APIs de catálogo tienen
 * límites duros (Discogs ~60/min, MusicBrainz 1 req/seg estricto). Sin esto una
 * sola búsqueda dispara decenas de requests juntos y cobra 429/503, y los
 * resultados quedan sin créditos ni rareza — justo lo que alimenta el score.
 * Ver docs/SOURCES.md
 */

const sleep = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms))

export type Limiter = <T>(fn: () => Promise<T>) => Promise<T>

/**
 * Serializa las llamadas dejando `minIntervalMs` entre arranques consecutivos.
 * El intervalo se mide desde que la request sale, no desde que responde, que es
 * como cuentan los rate limits. Un error no corta la cola.
 */
export function createLimiter(minIntervalMs: number): Limiter {
  let tail: Promise<void> = Promise.resolve()

  return <T>(fn: () => Promise<T>): Promise<T> => {
    const slot = tail
    tail = slot.then(() => sleep(minIntervalMs))
    return slot.then(fn)
  }
}
