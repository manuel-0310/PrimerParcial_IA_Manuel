import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { CanvasTexture, SRGBColorSpace } from 'three'
import type { Group } from 'three'
import { useSimStore } from '../store/simStore'
import { BEAT } from './celebration'

const CREAM = '#f4ead2'
const BLACK = '#241f1a'

const CROWN_RADIUS = 0.145
const CROWN_HEIGHT = 0.1
const BRIM_RADIUS = 0.44
const BRIM_HEIGHT = 0.022

const CROWN_TEX_W = 256
const CROWN_TEX_H = 160
const BRIM_TEX_SIZE = 320

/** Horizontal bands + one woven "lace" band — the crisscross trim of the real hat. */
function drawCrownTexture(ctx: CanvasRenderingContext2D, w: number, h: number) {
  ctx.fillStyle = CREAM
  ctx.fillRect(0, 0, w, h)

  const bands = 7
  const bandH = h / bands
  for (let i = 0; i < bands; i++) {
    if (i % 2 === 0) continue
    ctx.fillStyle = BLACK
    ctx.fillRect(0, i * bandH, w, bandH + 1)
  }

  // Lace band: a zigzag crisscross woven through the middle band, cream on black.
  const laceBand = 3
  const y0 = laceBand * bandH
  const y1 = y0 + bandH
  ctx.strokeStyle = CREAM
  ctx.lineWidth = bandH * 0.22
  ctx.lineCap = 'round'
  const repeats = 12
  const step = w / repeats
  ctx.beginPath()
  for (let k = 0; k < repeats; k++) {
    const x = k * step
    if (k % 2 === 0) {
      ctx.moveTo(x, y0)
      ctx.lineTo(x + step, y1)
    } else {
      ctx.moveTo(x, y1)
      ctx.lineTo(x + step, y0)
    }
  }
  ctx.stroke()
}

/** Concentric black/cream rings plus a scalloped trim ring at the outer edge. */
function drawBrimTexture(ctx: CanvasRenderingContext2D, size: number) {
  const cx = size / 2
  const cy = size / 2
  const maxR = size / 2

  ctx.fillStyle = CREAM
  ctx.fillRect(0, 0, size, size)

  const ringCount = 8
  for (let i = 0; i < ringCount; i++) {
    if (i % 2 === 0) continue
    const rOuter = maxR * (1 - i / ringCount)
    const rInner = maxR * (1 - (i + 0.5) / ringCount)
    ctx.fillStyle = BLACK
    ctx.beginPath()
    ctx.arc(cx, cy, rOuter, 0, Math.PI * 2)
    ctx.arc(cx, cy, rInner, 0, Math.PI * 2, true)
    ctx.fill('evenodd')
  }

  // Scalloped border — the toothy black edge that frames the whole brim.
  // The zigzag path alone would fill as a solid disk (it winds once around
  // the center), so an inner circle is added as an evenodd "hole" to keep
  // only the thin ring between it and the teeth.
  const teeth = 44
  const rOut = maxR * 0.985
  const rIn = maxR * 0.88
  ctx.fillStyle = BLACK
  ctx.beginPath()
  for (let k = 0; k <= teeth * 2; k++) {
    const ang = (k / (teeth * 2)) * Math.PI * 2
    const r = k % 2 === 0 ? rOut : rIn
    const x = cx + Math.cos(ang) * r
    const y = cy + Math.sin(ang) * r
    if (k === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  }
  ctx.closePath()
  ctx.moveTo(cx + rIn, cy)
  ctx.arc(cx, cy, rIn, 0, Math.PI * 2, true)
  ctx.closePath()
  ctx.fill('evenodd')
}

/**
 * Sombrero vueltiao — always worn: a banded crown with a woven lace trim, a
 * rounded dome (the same texture wraps onto it, reading as concentric rings
 * from above), and a wide brim ringed in black with a scalloped border.
 */
export function SombreroVueltiao() {
  const wiggle = useRef<Group>(null)
  const amp = useRef(0)
  const danceT = useRef(0)
  const celebrating = useSimStore((s) => s.celebrating)

  const crownTexture = useMemo(() => {
    const canvas = document.createElement('canvas')
    canvas.width = CROWN_TEX_W
    canvas.height = CROWN_TEX_H
    drawCrownTexture(canvas.getContext('2d')!, CROWN_TEX_W, CROWN_TEX_H)
    const tex = new CanvasTexture(canvas)
    tex.colorSpace = SRGBColorSpace
    return tex
  }, [])

  const brimTexture = useMemo(() => {
    const canvas = document.createElement('canvas')
    canvas.width = BRIM_TEX_SIZE
    canvas.height = BRIM_TEX_SIZE
    drawBrimTexture(canvas.getContext('2d')!, BRIM_TEX_SIZE)
    const tex = new CanvasTexture(canvas)
    tex.colorSpace = SRGBColorSpace
    return tex
  }, [])

  useFrame((state, rawDelta) => {
    const w = wiggle.current
    if (!w) return
    const dt = Math.min(0.05, rawDelta)
    const elapsed = state.clock.elapsedTime

    const target = celebrating ? 1 : 0
    amp.current += (target - amp.current) * Math.min(1, dt * (celebrating ? 5 : 3))
    const a = amp.current
    if (celebrating) danceT.current += dt
    else if (a < 0.01) danceT.current = 0
    const t = danceT.current

    // Level and steady while working; tips and flops on the beat once the party starts.
    w.rotation.z = Math.sin(elapsed * 1.2) * 0.025 * (1 - a) + Math.sin(t * BEAT) * 0.16 * a
    w.rotation.x = Math.cos(elapsed * 0.9) * 0.02 * (1 - a) + Math.cos(t * BEAT * 0.8) * 0.12 * a
  })

  return (
    <group ref={wiggle} position={[0, 0.46, 0]}>
      {/* Brim — black underside/edge, ringed top face. */}
      <mesh castShadow position={[0, 0, 0]}>
        <cylinderGeometry args={[BRIM_RADIUS, BRIM_RADIUS, BRIM_HEIGHT, 40]} />
        <meshStandardMaterial attach="material-0" color={BLACK} roughness={0.7} />
        <meshStandardMaterial attach="material-1" map={brimTexture} roughness={0.7} />
        <meshStandardMaterial attach="material-2" color={CREAM} roughness={0.7} />
      </mesh>

      {/* Hat band, where the crown meets the brim. */}
      <mesh castShadow position={[0, BRIM_HEIGHT / 2 + 0.015, 0]}>
        <cylinderGeometry args={[CROWN_RADIUS + 0.006, CROWN_RADIUS + 0.006, 0.03, 24]} />
        <meshStandardMaterial color={BLACK} roughness={0.7} />
      </mesh>

      {/* Crown, wrapped in the banded + lace texture. */}
      <mesh castShadow position={[0, BRIM_HEIGHT / 2 + 0.03 + CROWN_HEIGHT / 2, 0]}>
        <cylinderGeometry args={[CROWN_RADIUS, CROWN_RADIUS, CROWN_HEIGHT, 24]} />
        <meshStandardMaterial map={crownTexture} roughness={0.75} />
      </mesh>

      {/* Rounded top — same texture reads as concentric rings from above. */}
      <mesh castShadow position={[0, BRIM_HEIGHT / 2 + 0.03 + CROWN_HEIGHT, 0]}>
        <sphereGeometry args={[CROWN_RADIUS, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshStandardMaterial map={crownTexture} roughness={0.75} />
      </mesh>
    </group>
  )
}
