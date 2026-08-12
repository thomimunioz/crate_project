/**
 * Formateo para la UI. Nada de dominio acá: solo cómo se lee un dato en pantalla.
 * La regla es que todo lo que sea número se lea de un vistazo y en mono.
 */

/** 1834 → "1.8k" · 1240000 → "1.2M". Los números redondos digen mejor. */
export function formatCount(n: number): string {
  if (n < 1000) return String(n)
  if (n < 1_000_000) {
    const k = n / 1000
    return `${k < 10 ? k.toFixed(1).replace(/\.0$/, '') : Math.round(k)}k`
  }
  const m = n / 1_000_000
  return `${m < 10 ? m.toFixed(1).replace(/\.0$/, '') : Math.round(m)}M`
}

/** 222 → "3:42". Duración de la fuente, útil para oler un mix de un track. */
export function formatDuration(sec?: number): string | undefined {
  if (!sec || sec <= 0) return undefined
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = Math.floor(sec % 60)
  const pad = (x: number): string => String(x).padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`
}

/** ISO → "26.08.11": sello de fecha, como el que te ponen atrás de la ficha. */
export function formatStamp(iso?: string): string | undefined {
  if (!iso) return undefined
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return undefined
  const p = (x: number): string => String(x).padStart(2, '0')
  return `${p(d.getFullYear() % 100)}.${p(d.getMonth() + 1)}.${p(d.getDate())}`
}

export type TierKey = 'gem' | 'strong' | 'worth' | 'deep'

export interface Tier {
  key: TierKey
  /** color del sticker / del canto de la ficha */
  bg: string
  /** tinta legible sobre ese color (todos pasan AA) */
  ink: string
}

/**
 * Tier visual del score. Los cortes espejan `scoreLabel()` de core/score.ts:
 * el texto sigue saliendo de ahí, acá solo se decide de qué color es el sticker.
 */
export function scoreTier(total: number): Tier {
  if (total >= 85) return { key: 'gem', bg: '#F0B24A', ink: '#151007' }
  if (total >= 70) return { key: 'strong', bg: '#6FB2A6', ink: '#151007' }
  if (total >= 55) return { key: 'worth', bg: '#B6A98F', ink: '#151007' }
  return { key: 'deep', bg: '#5E543F', ink: '#ECE2D0' }
}

/** Saca el emoji que trae `scoreLabel()` para poder maquetarlo aparte. */
export function splitLabel(label: string): { icon?: string; text: string } {
  const m = label.match(/^(\P{L}+?)\s+(.*)$/u)
  if (!m) return { text: label }
  const icon = m[1]?.trim()
  return { icon: icon || undefined, text: m[2] ?? label }
}
