/**
 * Tempo — la octava del BPM y el prior del oído.
 *
 * El DSP se equivoca de octava hacia arriba, y mucho. Medido sobre 247 temas
 * del crate de Thomas (`docs/benchmarks/2026-09-19-digging-a-mano/bpm_octave_dataset.json`):
 * de 120 con BPM crudo > 115, 95 eran el doble (79%); de 127 con crudo ≤ 115,
 * 123 estaban bien. Sin plegar, el crudo acierta 147/247 (60%); plegado contra
 * el rango 58–115 con 3% de tolerancia en el borde, 228/247 (92%).
 *
 * División de trabajo (no negociable, ver contracts C2/C5): el backend devuelve
 * EVIDENCIA de audio (candidatos ×0.5/×1/×2 con su support, `ambiguous`), sin
 * ningún gusto personal. El prior PERSONAL —qué tempos guarda este usuario—
 * vive acá, en el cliente, sale de la affinity (`tasteTempoRange`) y se dice en
 * el "Why this?". Un valor plegado nunca pisa al analizado: se guarda con
 * `method: 'inferred'` y el crudo queda como alternativa (provenance por dato).
 */

export interface BpmAlternative {
  value: number
  /** evidencia de audio para ese candidato, 0..1 (autocorrelación + backbeat) */
  support: number
}

export interface TempoRange {
  min: number
  max: number
}

export interface FoldedBpm {
  value: number
  /** true si se eligió otra octava que la que trajo el DSP */
  folded: boolean
  /** la línea del Why this ("76 BPM · analizado 152, plegado a tu rango 58–115") */
  reason?: string
}

/**
 * Rango por defecto cuando el crate todavía no enseñó nada. Medido sobre 247
 * temas de Thomas: p5 = 62, p95 = 118; 25 arriba de 115 real, 2 abajo de 58.
 * Es un dato del usuario, no una regla de CRATE: `affinity.ts::tasteTempoRange`
 * lo reemplaza en cuanto hay buckets de BPM suficientes.
 */
export const DEFAULT_TEMPO_PRIOR: TempoRange = { min: 58, max: 115 }

/**
 * Tolerancia en el borde del rango. El DSP cuantiza el tempo a lags enteros
 * (117.5, 123, 129.2…): un 117.5 con rango hasta 115 es "115 y pico", no una
 * octava arriba. Con 3% el umbral de confianza deja de importar (92.3% en el
 * dataset con cualquier corte entre 0.5 y 0.8).
 */
const BORDE = 0.03

/**
 * Sin `alternatives` (backend viejo), solo se pliega si el DSP no estaba muy
 * seguro. Los mal leídos promediaron 0.42 de confianza; los bien leídos, 0.53.
 * 0.8 = "salvo evidencia fuerte".
 */
const MAX_CONFIANZA_PARA_PLEGAR = 0.8

/** Cuánta más evidencia tiene que tener el crudo que la octava vecina para dejarlo. */
const VENTAJA_FUERTE = 1.5

const enRangoConBorde = (v: number, r: TempoRange): boolean =>
  v >= r.min * (1 - BORDE) && v <= r.max * (1 + BORDE)

const enRango = (v: number, r: TempoRange): boolean => v >= r.min && v <= r.max

const redondear = (v: number): number => Math.round(v * 10) / 10

/**
 * Elige la octava del BPM que cae en el rango del usuario.
 *
 * - Si `value` ya cae en el rango (con borde), se deja.
 * - Con `alternatives` del backend (C2): se elige la de mayor support que caiga
 *   en el rango, salvo que el crudo tenga una ventaja fuerte de evidencia.
 * - Sin alternativas: ×0.5 o ×2 si cae en el rango y la confianza no es alta.
 *
 * Devuelve siempre la razón cuando pliega, para que el Why this la muestre.
 */
export function foldBpm(
  value: number,
  alternatives: BpmAlternative[] | undefined,
  prior: TempoRange = DEFAULT_TEMPO_PRIOR,
  opts: { confidence?: number } = {},
): FoldedBpm {
  if (!(value > 0)) return { value, folded: false }
  if (enRangoConBorde(value, prior)) return { value, folded: false }

  const razon = (elegido: number): string =>
    `${Math.round(elegido)} BPM · analizado ${Math.round(value)}, plegado a tu rango ${prior.min}–${prior.max}`

  if (alternatives?.length) {
    const crudo = alternatives.find((a) => Math.abs(a.value - value) < 0.5)
    const adentro = alternatives
      .filter((a) => enRango(a.value, prior) && Math.abs(a.value - value) >= 0.5)
      .sort((a, b) => b.support - a.support)[0]
    if (!adentro) return foldSinEvidencia(value, prior, opts.confidence, razon)
    if (crudo && crudo.support > adentro.support * VENTAJA_FUERTE) {
      return { value, folded: false }
    }
    return { value: redondear(adentro.value), folded: true, reason: razon(adentro.value) }
  }

  return foldSinEvidencia(value, prior, opts.confidence, razon)
}

function foldSinEvidencia(
  value: number,
  prior: TempoRange,
  confidence: number | undefined,
  razon: (v: number) => string,
): FoldedBpm {
  if (confidence != null && confidence >= MAX_CONFIANZA_PARA_PLEGAR) return { value, folded: false }
  const mitad = value / 2
  const doble = value * 2
  if (value > prior.max && enRango(mitad, prior)) {
    return { value: redondear(mitad), folded: true, reason: razon(mitad) }
  }
  if (value < prior.min && enRango(doble, prior)) {
    return { value: redondear(doble), folded: true, reason: razon(doble) }
  }
  return { value, folded: false }
}

/** ¿`value` pega con `target` ± tol, tolerando la octava (×0.5 / ×2)? */
export function bpmMatches(value: number, target: number, tol: number): boolean {
  return (
    Math.abs(value - target) <= tol ||
    Math.abs(value / 2 - target) <= tol ||
    Math.abs(value * 2 - target) <= tol
  )
}

/**
 * ¿`value` cae en [lo, hi]? 'exact' si sí, 'octave' si lo hace su mitad o su
 * doble (el filtro no debería descartar un 152 leído que es un 76 real), 'no'.
 */
export function bpmWithinRange(value: number, lo: number, hi: number): 'exact' | 'octave' | 'no' {
  const dentro = (v: number): boolean => v >= lo && v <= hi
  if (dentro(value)) return 'exact'
  if (dentro(value / 2) || dentro(value * 2)) return 'octave'
  return 'no'
}
