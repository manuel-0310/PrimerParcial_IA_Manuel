/** Shared timing so body and face dance on the same beat. */

/** Beat of the dance, in radians per second (~2 hops/second). */
export const BEAT = Math.PI * 2 * 2.05
export const HOP_FREQ = 2.05
export const HOP_HEIGHT = 0.3
/** Seconds of opening twirl before the dance settles into the shimmy loop. */
export const TWIRL_DUR = 1.5

export function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
}

export function smoothstep(edge0: number, edge1: number, x: number): number {
  const t = Math.min(1, Math.max(0, (x - edge0) / (edge1 - edge0)))
  return t * t * (3 - 2 * t)
}
