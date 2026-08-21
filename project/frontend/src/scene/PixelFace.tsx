import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { CanvasTexture, NearestFilter, SRGBColorSpace } from 'three'
import type { MeshStandardMaterial } from 'three'
import { useSimStore } from '../store/simStore'
import { BEAT } from './celebration'

const GRID_W = 16
const GRID_H = 10
const SCREEN_BG = '#060d18'

type FaceName = 'happy' | 'blink' | 'partyA' | 'partyB' | 'worried' | 'think1' | 'think2' | 'think3'

/** 16x10 sprites — '#' is a lit pixel, '.' is dark screen. */
const FACES: Record<FaceName, { rows: string[]; color: string }> = {
  happy: {
    color: '#22d3ee',
    rows: [
      '................',
      '...##......##...',
      '...##......##...',
      '...##......##...',
      '................',
      '................',
      '.#............#.',
      '..#..........#..',
      '...##########...',
      '................',
    ],
  },
  blink: {
    color: '#22d3ee',
    rows: [
      '................',
      '................',
      '................',
      '..####....####..',
      '................',
      '................',
      '.#............#.',
      '..#..........#..',
      '...##########...',
      '................',
    ],
  },
  // Cheering: caret eyes and a mouth that opens on the beat.
  partyA: {
    color: '#fde047',
    rows: [
      '................',
      '...#........#...',
      '..#.#......#.#..',
      '................',
      '....########....',
      '...##########...',
      '...##########...',
      '....########....',
      '................',
      '................',
    ],
  },
  partyB: {
    color: '#fde047',
    rows: [
      '................',
      '...#........#...',
      '..#.#......#.#..',
      '................',
      '................',
      '....########....',
      '...##########...',
      '....########....',
      '................',
      '................',
    ],
  },
  // Thinking: eyes up, and a row of dots that fills in while UCS grinds away.
  think1: {
    color: '#93c5fd',
    rows: [
      '................',
      '..####....####..',
      '..#..#....#..#..',
      '..####....####..',
      '................',
      '................',
      '................',
      '...##...........',
      '...##...........',
      '................',
    ],
  },
  think2: {
    color: '#93c5fd',
    rows: [
      '................',
      '..####....####..',
      '..#..#....#..#..',
      '..####....####..',
      '................',
      '................',
      '................',
      '...##..##.......',
      '...##..##.......',
      '................',
    ],
  },
  think3: {
    color: '#93c5fd',
    rows: [
      '................',
      '..####....####..',
      '..#..#....#..#..',
      '..####....####..',
      '................',
      '................',
      '................',
      '...##..##..##...',
      '...##..##..##...',
      '................',
    ],
  },
  worried: {
    color: '#f59e0b',
    rows: [
      '................',
      '..#..#....#..#..',
      '...##......##...',
      '..#..#....#..#..',
      '................',
      '................',
      '...##########...',
      '..#..........#..',
      '.#............#.',
      '................',
    ],
  },
}

function drawFace(ctx: CanvasRenderingContext2D, face: FaceName) {
  const { rows, color } = FACES[face]
  ctx.fillStyle = SCREEN_BG
  ctx.fillRect(0, 0, GRID_W, GRID_H)
  ctx.fillStyle = color
  rows.forEach((row, y) => {
    for (let x = 0; x < row.length; x++) {
      if (row[x] === '#') ctx.fillRect(x, y, 1, 1)
    }
  })
}

/**
 * Pixel-art face on the robot's front screen. Blinks while working, switches to
 * a cheering sprite on the beat during the dance, and frowns on warnings.
 */
export function PixelFace() {
  const material = useRef<MeshStandardMaterial>(null)
  const current = useRef<FaceName | null>(null)
  const amp = useRef(0)
  const danceT = useRef(0)

  const celebrating = useSimStore((s) => s.celebrating)
  const solving = useSimStore((s) => s.solving)
  const tone = useSimStore((s) => s.speech?.tone)

  const { texture, ctx } = useMemo(() => {
    const canvas = document.createElement('canvas')
    canvas.width = GRID_W
    canvas.height = GRID_H
    const context = canvas.getContext('2d')!
    context.imageSmoothingEnabled = false
    drawFace(context, 'happy')
    const tex = new CanvasTexture(canvas)
    // Nearest filtering everywhere — this is what keeps the pixels crisp.
    tex.magFilter = NearestFilter
    tex.minFilter = NearestFilter
    tex.generateMipmaps = false
    tex.colorSpace = SRGBColorSpace
    return { texture: tex, ctx: context }
  }, [])

  useFrame((state, rawDelta) => {
    const dt = Math.min(0.05, rawDelta)
    const elapsed = state.clock.elapsedTime

    const target = celebrating ? 1 : 0
    amp.current += (target - amp.current) * Math.min(1, dt * (celebrating ? 5 : 3))
    if (celebrating) danceT.current += dt
    else if (amp.current < 0.01) danceT.current = 0
    const t = danceT.current

    let face: FaceName
    if (solving) {
      face = (['think1', 'think2', 'think3'] as const)[Math.floor(elapsed / 0.35) % 3]
    } else if (celebrating) {
      face = Math.sin(t * BEAT) > 0 ? 'partyA' : 'partyB'
    } else if (tone === 'warn') {
      face = 'worried'
    } else {
      // Blink for ~0.13s every 3.7s.
      face = elapsed % 3.7 < 0.13 ? 'blink' : 'happy'
    }

    if (face !== current.current) {
      current.current = face
      drawFace(ctx, face)
      texture.needsUpdate = true
    }

    if (material.current) {
      material.current.emissiveIntensity =
        1.15 + amp.current * (1.2 + Math.sin(t * BEAT) * 0.7)
    }
  })

  return (
    <group position={[0, 0.2, 0.276]}>
      {/* Bezel — a dark frame so the screen reads as a screen. */}
      <mesh position={[0, 0, 0.012]}>
        <boxGeometry args={[0.48, 0.31, 0.03]} />
        <meshStandardMaterial color="#0b1220" roughness={0.5} metalness={0.35} />
      </mesh>
      <mesh position={[0, 0, 0.031]}>
        <planeGeometry args={[0.44, 0.275]} />
        <meshStandardMaterial
          ref={material}
          map={texture}
          emissiveMap={texture}
          emissive="#ffffff"
          emissiveIntensity={1.15}
          toneMapped={false}
        />
      </mesh>
    </group>
  )
}
