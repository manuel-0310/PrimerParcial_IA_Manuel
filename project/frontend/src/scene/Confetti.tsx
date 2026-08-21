import { useEffect, useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { Color, Euler, InstancedMesh, Object3D, Vector3 } from 'three'
import { useSimStore } from '../store/simStore'

const COUNT = 260
/** Share of the particles launched from the robot; the rest rains from above. */
const BURST_RATIO = 0.55
const GRAVITY = 7.4
const AIR_DRAG = 0.55
const FLOOR_Y = 0.04

const PALETTE = [
  '#22d3ee',
  '#facc15',
  '#e879f9',
  '#4ade80',
  '#fb923c',
  '#60a5fa',
  '#f87171',
  '#ffffff',
]

interface Particle {
  pos: Vector3
  vel: Vector3
  rot: Euler
  spin: Vector3
  flutterPhase: number
  flutterFreq: number
  flutterAmp: number
  delay: number
  life: number
  ttl: number
  scale: number
  settled: boolean
  live: boolean
}

function makeParticle(): Particle {
  return {
    pos: new Vector3(),
    vel: new Vector3(),
    rot: new Euler(),
    spin: new Vector3(),
    flutterPhase: 0,
    flutterFreq: 0,
    flutterAmp: 0,
    delay: 0,
    life: 0,
    ttl: 0,
    scale: 1,
    settled: false,
    live: false,
  }
}

const rand = (min: number, max: number) => min + Math.random() * (max - min)

/**
 * One burst around `origin`: a cannon shot from the robot in three waves, plus
 * a slower rain over the room that keeps going after the shot lands.
 */
function armBurst(particles: Particle[], mesh: InstancedMesh, origin: [number, number, number]) {
  const color = new Color()
  const burstCount = Math.floor(COUNT * BURST_RATIO)

  particles.forEach((p, i) => {
    p.life = 0
    p.settled = false
    p.live = true
    p.rot.set(rand(0, Math.PI * 2), rand(0, Math.PI * 2), rand(0, Math.PI * 2))
    p.spin.set(rand(-9, 9), rand(-9, 9), rand(-9, 9))
    p.flutterPhase = rand(0, Math.PI * 2)
    p.flutterFreq = rand(4, 9)
    p.scale = rand(0.7, 1.35)

    if (i < burstCount) {
      // Cannon shot: three waves 0.75 s apart.
      const wave = i % 3
      const theta = rand(0, Math.PI * 2)
      const spread = rand(1.4, 4.2)
      p.pos.set(origin[0], origin[1] + 0.5, origin[2])
      p.vel.set(Math.cos(theta) * spread, rand(4.2, 6.6), Math.sin(theta) * spread)
      p.delay = wave * 0.75 + rand(0, 0.14)
      p.ttl = rand(3.2, 4.8)
      p.flutterAmp = rand(1.5, 4)
    } else {
      // Slow rain over the surrounding floor.
      const theta = rand(0, Math.PI * 2)
      const radius = rand(0.5, 5.5)
      p.pos.set(
        origin[0] + Math.cos(theta) * radius,
        rand(5.5, 7.5),
        origin[2] + Math.sin(theta) * radius,
      )
      p.vel.set(rand(-0.4, 0.4), rand(-1.4, -0.5), rand(-0.4, 0.4))
      p.delay = rand(0.2, 3.4)
      p.ttl = rand(4.5, 6.5)
      p.flutterAmp = rand(2.5, 5.5)
    }

    color.set(PALETTE[i % PALETTE.length])
    mesh.setColorAt(i, color)
  })

  if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
}

export function Confetti() {
  const ref = useRef<InstancedMesh>(null)
  const seed = useSimStore((s) => s.celebrationSeed)
  const particles = useMemo(() => Array.from({ length: COUNT }, makeParticle), [])
  const dummy = useMemo(() => new Object3D(), [])

  useEffect(() => {
    const mesh = ref.current
    if (!mesh) return
    if (seed === 0) {
      // RESET while celebrating: drop every particle.
      particles.forEach((p) => {
        p.live = false
      })
      return
    }
    const origin = useSimStore.getState().runtime?.robotPosition ?? [0, 0.35, 0]
    armBurst(particles, mesh, origin as [number, number, number])
  }, [seed, particles])

  useFrame((_, rawDelta) => {
    const mesh = ref.current
    if (!mesh) return
    const dt = Math.min(0.05, rawDelta)
    let anyLive = false

    for (let i = 0; i < particles.length; i++) {
      const p = particles[i]

      if (!p.live || p.delay > 0) {
        if (p.live) {
          p.delay -= dt
          anyLive = true
        }
        dummy.scale.setScalar(0)
        dummy.position.set(0, -100, 0)
        dummy.rotation.set(0, 0, 0)
        dummy.updateMatrix()
        mesh.setMatrixAt(i, dummy.matrix)
        continue
      }

      p.life += dt
      if (p.life >= p.ttl) {
        p.live = false
        dummy.scale.setScalar(0)
        dummy.position.set(0, -100, 0)
        dummy.updateMatrix()
        mesh.setMatrixAt(i, dummy.matrix)
        continue
      }
      anyLive = true

      if (p.settled) {
        // Lie flat on the floor while fading out.
        const k = Math.min(1, dt * 6)
        p.rot.x += (-Math.PI / 2 - p.rot.x) * k
        p.rot.z += (0 - p.rot.z) * k
      } else {
        p.vel.y -= GRAVITY * dt
        p.vel.x -= p.vel.x * AIR_DRAG * dt
        p.vel.z -= p.vel.z * AIR_DRAG * dt
        // Sideways drift; without it the pieces fall like sand.
        p.vel.x += Math.sin(p.life * p.flutterFreq + p.flutterPhase) * p.flutterAmp * dt
        p.vel.z += Math.cos(p.life * p.flutterFreq * 0.8 + p.flutterPhase) * p.flutterAmp * dt
        p.pos.addScaledVector(p.vel, dt)
        p.rot.x += p.spin.x * dt
        p.rot.y += p.spin.y * dt
        p.rot.z += p.spin.z * dt
        if (p.pos.y <= FLOOR_Y) {
          p.pos.y = FLOOR_Y
          p.settled = true
        }
      }

      const fadeIn = Math.min(1, p.life / 0.12)
      const fadeOut = Math.min(1, (p.ttl - p.life) / 0.8)
      dummy.position.copy(p.pos)
      dummy.rotation.copy(p.rot)
      dummy.scale.setScalar(p.scale * fadeIn * fadeOut)
      dummy.updateMatrix()
      mesh.setMatrixAt(i, dummy.matrix)
    }

    mesh.instanceMatrix.needsUpdate = true
    mesh.visible = anyLive
  })

  return (
    <instancedMesh ref={ref} args={[undefined, undefined, COUNT]} frustumCulled={false} visible={false}>
      <boxGeometry args={[0.13, 0.018, 0.085]} />
      <meshStandardMaterial roughness={0.45} metalness={0.15} toneMapped={false} />
    </instancedMesh>
  )
}
