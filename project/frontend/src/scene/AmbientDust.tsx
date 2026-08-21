import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { Color, InstancedMesh, Object3D } from 'three'
import { computeWalkableBounds } from '../lib/grid'
import { useSimStore } from '../store/simStore'

const COUNT = 70
const MIN_Y = 0.18
const MAX_Y = 1.5
/** Fraction of the vertical range spent fading in/out at each end, so motes
 * never visibly pop when they wrap back to the bottom. */
const FADE_BAND = 0.16

interface Mote {
  baseX: number
  baseZ: number
  y: number
  riseSpeed: number
  wanderFreq: number
  wanderPhase: number
  scale: number
}

function rand(min: number, max: number): number {
  return min + Math.random() * (max - min)
}

/**
 * Soft glowing dust drifting through the room — slow upward rise with a gentle
 * sideways wander, wrapping back to the floor once it clears the ceiling.
 * Color is boosted past 1.0 so it blooms into a faint halo (see Effects.tsx).
 */
export function AmbientDust() {
  const ref = useRef<InstancedMesh>(null)
  const scenario = useSimStore((s) => s.scenario)
  const dummy = useMemo(() => new Object3D(), [])
  const glowColor = useMemo(() => new Color('#bae6fd').multiplyScalar(2.6), [])

  const bounds = useMemo(() => {
    if (!scenario) return null
    const b = computeWalkableBounds(scenario.layout)
    const pad = b.cellSize * 0.6
    return { minX: b.minX + pad, maxX: b.maxX - pad, minZ: b.minZ + pad, maxZ: b.maxZ - pad }
  }, [scenario])

  const motes = useMemo<Mote[]>(() => {
    if (!bounds) return []
    return Array.from({ length: COUNT }, () => ({
      baseX: rand(bounds.minX, bounds.maxX),
      baseZ: rand(bounds.minZ, bounds.maxZ),
      y: rand(MIN_Y, MAX_Y),
      riseSpeed: rand(0.025, 0.07),
      wanderFreq: rand(0.3, 0.8),
      wanderPhase: rand(0, Math.PI * 2),
      scale: rand(0.6, 1.4),
    }))
  }, [bounds])

  useFrame((state, rawDelta) => {
    const mesh = ref.current
    if (!mesh || motes.length === 0) return
    const dt = Math.min(0.05, rawDelta)
    const elapsed = state.clock.elapsedTime
    const fadeDist = (MAX_Y - MIN_Y) * FADE_BAND

    for (let i = 0; i < motes.length; i++) {
      const m = motes[i]
      m.y += m.riseSpeed * dt
      if (m.y > MAX_Y) m.y = MIN_Y

      const wobbleX = Math.sin(elapsed * m.wanderFreq + m.wanderPhase) * 0.18
      const wobbleZ = Math.cos(elapsed * m.wanderFreq * 0.8 + m.wanderPhase) * 0.18
      const fade = Math.min(1, (m.y - MIN_Y) / fadeDist, (MAX_Y - m.y) / fadeDist)

      dummy.position.set(m.baseX + wobbleX, m.y, m.baseZ + wobbleZ)
      dummy.scale.setScalar(m.scale * Math.max(0, fade))
      dummy.updateMatrix()
      mesh.setMatrixAt(i, dummy.matrix)
    }
    mesh.instanceMatrix.needsUpdate = true
  })

  if (!bounds || motes.length === 0) return null

  return (
    <instancedMesh ref={ref} args={[undefined, undefined, COUNT]} frustumCulled={false}>
      <sphereGeometry args={[0.02, 6, 6]} />
      <meshBasicMaterial color={glowColor} transparent opacity={0.65} toneMapped={false} />
    </instancedMesh>
  )
}
