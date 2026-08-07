/**
 * Cache persistente de respuestas de catálogo (Discogs, MusicBrainz).
 *
 * Los datos de catálogo casi no cambian y las APIs están limitadas al segundo:
 * guardarlos en IndexedDB evita repagar el mismo lookup entre búsquedas y entre
 * sesiones. Es lo que hace que la segunda búsqueda parecida sea instantánea.
 */
import { db } from './crateIndex'

export const DAY_MS = 86_400_000
export const WEEK_MS = 7 * DAY_MS

export interface CacheRow {
  key: string
  value: unknown
  expiresAt: number
}

/** Devuelve el valor cacheado vigente, o corre `fn`, lo guarda y lo devuelve. */
export async function cached<T>(key: string, ttlMs: number, fn: () => Promise<T>): Promise<T> {
  const hit = await db.cache.get(key)
  if (hit && hit.expiresAt > Date.now()) return hit.value as T

  const value = await fn()
  await db.cache.put({ key, value, expiresAt: Date.now() + ttlMs })
  return value
}

/** Borra las entradas vencidas. Se llama al iniciar; el cache no se purga solo. */
export async function purgeExpired(): Promise<number> {
  return db.cache.where('expiresAt').below(Date.now()).delete()
}
