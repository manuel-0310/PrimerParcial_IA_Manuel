import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { Color, MathUtils } from 'three'
import type { Group, PointLight } from 'three'
import { useSimStore } from '../store/simStore'
import { BEAT, HOP_FREQ, HOP_HEIGHT, TWIRL_DUR, easeInOutCubic, smoothstep } from './celebration'
import { PixelFace } from './PixelFace'
import { SombreroVueltiao } from './SombreroVueltiao'
import { SpeechBubble } from './SpeechBubble'

/** Resting shoulder angle — arms droop when the robot is just working. */
const ARM_REST = 0.38

/** World units/sec at which the stride reaches full swing (≈ cell_size / MS_PER_CELL at 1x). */
const WALK_VELOCITY_REF = 2.3
/** Peak hip swing while marching, in radians. */
const STRIDE_ANGLE = 0.5
/** Strides per world unit travelled — ties cadence to distance, not wall-clock time. */
const STRIDE_RATE = 2.4

// Leg geometry — shared by the JSX below and the ground-height calculation,
// so the two can never drift out of sync if the legs are resized again.
const HIP_Y = -0.02
const THIGH_LEN = 0.34
const FOOT_CENTER_Y = -0.38
const FOOT_HEIGHT = 0.08
const GROUND_CLEARANCE = 0.008

/**
 * The runtime always reports robotPosition.y as a flat 0.35 (see simStore /
 * executor) — it was never meant as a real ground height, just a hover
 * placeholder. Now that the legs actually reach the floor, render at a fixed
 * height derived from the leg geometry instead, so the feet plant on the
 * tiles rather than clipping through them.
 */
const GROUND_Y = GROUND_CLEARANCE - (HIP_Y + FOOT_CENTER_Y - FOOT_HEIGHT / 2)

/** Mario-style item-get hop: raised fist + tucked legs + a quick vertical bounce. */
const PICKUP_HOP_DURATION = 0.45
const PICKUP_HOP_HEIGHT = 0.22
const PICKUP_ARM_RAISE = 1.7
const PICKUP_LEG_TUCK = 0.6

export function Robot() {
  const group = useRef<Group>(null)
  const dancer = useRef<Group>(null)
  const armL = useRef<Group>(null)
  const armR = useRef<Group>(null)
  const legL = useRef<Group>(null)
  const legR = useRef<Group>(null)
  const partyLight = useRef<PointLight>(null)

  /** 0 = working, 1 = full celebration. Eased so the dance never snaps in/out. */
  const amp = useRef(0)
  const danceT = useRef(0)
  const partyColor = useMemo(() => new Color(), [])

  /** Walk-cycle state, driven by measured velocity rather than a running flag. */
  const prevPos = useRef<[number, number] | null>(null)
  const walkAmp = useRef(0)
  const walkPhase = useRef(0)

  /** Pickup-hop state: a one-shot envelope timed from the last seen trigger. */
  const lastPickupSeed = useRef(0)
  const pickupClock = useRef(-Infinity)

  const pos = useSimStore(
    (s) => s.runtime?.robotPosition ?? ([0, 0.35, 0] as [number, number, number]),
  )
  const yaw = useSimStore((s) => s.runtime?.robotYaw ?? 0)
  const celebrating = useSimStore((s) => s.celebrating)
  const pickupSeed = useSimStore((s) => s.pickupSeed)

  useFrame((state, rawDelta) => {
    const g = group.current
    if (!g) return
    const dt = Math.min(0.05, rawDelta)
    const elapsed = state.clock.elapsedTime

    g.position.x = pos[0]
    g.position.y = GROUND_Y
    g.position.z = pos[2]
    g.rotation.y = yaw

    // Ease the celebration amplitude — in a bit faster than it eases out.
    const target = celebrating ? 1 : 0
    amp.current += (target - amp.current) * Math.min(1, dt * (celebrating ? 5 : 3))
    const a = amp.current
    if (celebrating) danceT.current += dt
    else if (a < 0.01) danceT.current = 0
    const t = danceT.current

    // Legs walk off measured ground speed, not a "running" flag — so pauses
    // between plan steps and in-place turns settle back to a neutral stance
    // on their own, and faster playback speed reads as a faster stride.
    const prev = prevPos.current
    const velocity = prev ? Math.hypot(pos[0] - prev[0], pos[2] - prev[1]) / dt : 0
    prevPos.current = [pos[0], pos[2]]
    const walkTarget = MathUtils.clamp(velocity / WALK_VELOCITY_REF, 0, 1)
    walkAmp.current += (walkTarget - walkAmp.current) * Math.min(1, dt * 8)
    walkPhase.current += dt * velocity * STRIDE_RATE
    const w = walkAmp.current
    const stride = Math.sin(walkPhase.current)

    // Pickup hop: a short one-shot envelope, restarted whenever pickupSeed
    // changes. Scaled by playback speed so it stays snappy at 3x.
    if (pickupSeed !== lastPickupSeed.current) {
      lastPickupSeed.current = pickupSeed
      pickupClock.current = elapsed
    }
    const hopSpeed = Math.max(0.25, useSimStore.getState().speed)
    const sincePickup = (elapsed - pickupClock.current) * hopSpeed
    const hop =
      sincePickup >= 0 && sincePickup < PICKUP_HOP_DURATION
        ? Math.sin((sincePickup / PICKUP_HOP_DURATION) * Math.PI)
        : 0

    // --- choreography -----------------------------------------------------
    // Hop with squash-and-stretch on landing.
    const hopU = (t * HOP_FREQ) % 1
    const air = Math.sin(hopU * Math.PI)
    const contact = Math.pow(1 - air, 2.5)
    // Opening move: two full turns, eased; then blend into the side-to-side shimmy.
    const twirl = easeInOutCubic(Math.min(1, t / TWIRL_DUR)) * Math.PI * 4
    const blend = smoothstep(TWIRL_DUR * 0.75, TWIRL_DUR * 1.3, t)
    const sway = Math.sin(t * BEAT * 0.5)

    const d = dancer.current
    if (d) {
      const idleBob = Math.sin(elapsed * 2) * 0.015 * (1 - a)
      d.position.y = idleBob + a * air * HOP_HEIGHT + hop * PICKUP_HOP_HEIGHT
      d.rotation.y = a * (twirl + blend * sway * 0.55)
      d.rotation.z = a * blend * sway * -0.18
      d.rotation.x = a * blend * Math.sin(t * BEAT) * 0.1
      d.scale.set(1 + a * 0.14 * contact, 1 - a * 0.2 * contact, 1 + a * 0.14 * contact)
    }

    // Arms: droop while working, punch the air on alternate beats while dancing.
    // The pickup hop blends the right arm past either of those, straight up.
    const waveR = Math.sin(t * BEAT)
    const waveL = Math.sin(t * BEAT + Math.PI)
    if (armR.current) {
      const armRRest = MathUtils.lerp(-ARM_REST, 1.05 + waveR * 0.55, a)
      armR.current.rotation.z = MathUtils.lerp(armRRest, PICKUP_ARM_RAISE, hop)
    }
    if (armL.current) {
      armL.current.rotation.z = MathUtils.lerp(ARM_REST, -(1.05 + waveL * 0.55), a)
    }

    // Legs: alternating march while translating, alternating kick while
    // dancing — plus a same-direction tuck for the pickup hop, since both
    // feet leave the ground together on a jump rather than alternating.
    // All three terms are safe to add outright: the robot only ever does one
    // of walk / dance / pickup at a time, so at most one is non-zero.
    if (legR.current) {
      legR.current.rotation.x =
        w * STRIDE_ANGLE * stride + a * 0.4 * Math.sin(t * BEAT) + hop * PICKUP_LEG_TUCK
    }
    if (legL.current) {
      legL.current.rotation.x =
        w * STRIDE_ANGLE * -stride + a * 0.4 * Math.sin(t * BEAT + Math.PI) + hop * PICKUP_LEG_TUCK
    }

    if (partyLight.current) {
      partyColor.setHSL((t * 0.32) % 1, 0.85, 0.6)
      partyLight.current.color.copy(partyColor)
      partyLight.current.intensity = a * 7
    }
  })

  return (
    <group ref={group} position={[pos[0], GROUND_Y, pos[2]]} rotation={[0, yaw, 0]}>
      {/* Dance transform lives on an inner group so plan movement stays exact. */}
      <group ref={dancer}>
        <mesh position={[0, 0.15, 0]} castShadow>
          <boxGeometry args={[0.55, 0.4, 0.55]} />
          <meshStandardMaterial color="#f1f5f9" roughness={0.35} metalness={0.2} />
        </mesh>
        <mesh castShadow position={[0, 0.4, 0]}>
          <boxGeometry args={[0.45, 0.12, 0.45]} />
          <meshStandardMaterial color="#e2e8f0" />
        </mesh>
        {/* Face screen looks along local +Z — yaw aligns +Z with movement direction */}
        <PixelFace />
        <SombreroVueltiao />

        {/* Arms — pivot at the shoulder, box extends outward from it. */}
        <group ref={armR} position={[0.3, 0.26, 0]}>
          <mesh castShadow position={[0.11, 0, 0]}>
            <boxGeometry args={[0.22, 0.1, 0.1]} />
            <meshStandardMaterial color="#cbd5e1" roughness={0.4} metalness={0.25} />
          </mesh>
          <mesh castShadow position={[0.25, 0, 0]}>
            <boxGeometry args={[0.11, 0.13, 0.13]} />
            <meshStandardMaterial color="#94a3b8" />
          </mesh>
        </group>
        <group ref={armL} position={[-0.3, 0.26, 0]}>
          <mesh castShadow position={[-0.11, 0, 0]}>
            <boxGeometry args={[0.22, 0.1, 0.1]} />
            <meshStandardMaterial color="#cbd5e1" roughness={0.4} metalness={0.25} />
          </mesh>
          <mesh castShadow position={[-0.25, 0, 0]}>
            <boxGeometry args={[0.11, 0.13, 0.13]} />
            <meshStandardMaterial color="#94a3b8" />
          </mesh>
        </group>

        {/* Legs — pivot at the hip, thigh + foot hang straight down from it. */}
        <group ref={legR} position={[0.15, HIP_Y, 0]}>
          <mesh castShadow position={[0, -THIGH_LEN / 2, 0]}>
            <boxGeometry args={[0.12, THIGH_LEN, 0.12]} />
            <meshStandardMaterial color="#cbd5e1" roughness={0.4} metalness={0.25} />
          </mesh>
          <mesh castShadow position={[0, FOOT_CENTER_Y, 0.02]}>
            <boxGeometry args={[0.14, FOOT_HEIGHT, 0.18]} />
            <meshStandardMaterial color="#0f172a" />
          </mesh>
        </group>
        <group ref={legL} position={[-0.15, HIP_Y, 0]}>
          <mesh castShadow position={[0, -THIGH_LEN / 2, 0]}>
            <boxGeometry args={[0.12, THIGH_LEN, 0.12]} />
            <meshStandardMaterial color="#cbd5e1" roughness={0.4} metalness={0.25} />
          </mesh>
          <mesh castShadow position={[0, FOOT_CENTER_Y, 0.02]}>
            <boxGeometry args={[0.14, FOOT_HEIGHT, 0.18]} />
            <meshStandardMaterial color="#0f172a" />
          </mesh>
        </group>
      </group>

      {/* Colour-cycling disco light, dark until the celebration starts. */}
      <pointLight ref={partyLight} position={[0, 0.9, 0]} intensity={0} distance={7} decay={2} />

      <SpeechBubble />
    </group>
  )
}
