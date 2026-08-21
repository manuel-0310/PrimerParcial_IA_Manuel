import { createSpeechDirector, failureLine, incompleteLine, successLine } from './dialogue'
import { applyStep, checkGoal, sleep } from './executor'
import { cellToWorld } from './grid'
import { useSimStore } from '../store/simStore'
import type { Scenario, SolveResponse } from '../types'

const API_URL = '/api/solve'

/** Base milliseconds to cross one grid cell at speed 1x — constant linear speed. */
const MS_PER_CELL = 420
/** Base milliseconds per radian of yaw turn at speed 1x. */
const MS_PER_RAD = 220
const ACTION_PAUSE_MS = 180

export async function fetchPlan(
  scenario: Scenario,
  signal?: AbortSignal,
): Promise<SolveResponse> {
  const res = await fetch(API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(scenario),
    signal,
  })
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${await res.text()}`)
  }
  return res.json()
}

export async function runPlan(): Promise<void> {
  const store = useSimStore.getState()
  const { scenario, runtime, plan } = store
  if (!scenario || !runtime || plan.length === 0) return

  store.setRunning(true)
  store.appendLog({ text: `[---] Executing plan (${plan.length} steps)...`, level: 'info' })

  let current = runtime
  const director = createSpeechDirector()

  for (let i = 0; i < plan.length; i++) {
    if (!useSimStore.getState().running) break
    const step = plan[i]
    const result = applyStep(scenario, current, step)
    const idx = String(i + 1).padStart(3, '0')

    if (!result.ok) {
      store.appendLog({ text: `[${idx}] ERROR: ${result.message}`, level: 'error' })
      store.setError(result.message)
      const oops = failureLine(result.message)
      store.say(oops.text, oops.tone, oops.hold)
      store.setRunning(false)
      return
    }

    if (result.pathCells && result.pathCells.length > 1) {
      await animateGridPath(result.pathCells, scenario.layout.cell_size)
      const live = useSimStore.getState().runtime
      if (live) {
        result.runtime.robotPosition = live.robotPosition
        result.runtime.robotYaw = live.robotYaw
      }
    }

    store.applyRuntime(result.runtime)
    store.setStepIndex(i + 1)
    store.appendLog({ text: `[${idx}] ${result.message}`, level: 'ok' })
    if (step.op === 'PICKUP') store.triggerPickupHop()
    const line = director.lineFor(scenario, step, current, result.runtime, i)
    if (line) store.say(line.text, line.tone, line.hold)
    current = result.runtime

    await sleep(ACTION_PAUSE_MS / Math.max(0.25, useSimStore.getState().speed))
  }

  if (checkGoal(scenario, current)) {
    store.appendLog({
      text: `[***] MISSION COMPLETE — all stations ONLINE (spent ${current.energySpent})`,
      level: 'ok',
    })
    const victory = successLine()
    store.say(victory.text, victory.tone, victory.hold)
    store.startCelebration()
  } else {
    store.appendLog({
      text: `[***] Plan finished but goal NOT satisfied`,
      level: 'warn',
    })
    const shrug = incompleteLine()
    store.say(shrug.text, shrug.tone, shrug.hold)
  }
  store.setRunning(false)
  store.setAnim([], null)
}

function normalizeAngle(a: number): number {
  while (a > Math.PI) a -= Math.PI * 2
  while (a < -Math.PI) a += Math.PI * 2
  return a
}

async function animateGridPath(cells: [number, number][], cellSize: number): Promise<void> {
  const points = cells.map(
    ([gx, gz]) => cellToWorld(gx, gz, cellSize) as [number, number, number],
  )

  for (let i = 0; i < points.length - 1; i++) {
    if (!useSimStore.getState().running) return
    const a = points[i]
    const b = points[i + 1]
    const dx = b[0] - a[0]
    const dz = b[2] - a[2]
    const targetYaw = Math.atan2(dx, dz)
    await rotateYawTo(targetYaw)
    await translateConstant(a, b)
  }
}

async function rotateYawTo(targetYaw: number): Promise<void> {
  const store = useSimStore.getState()
  const startYaw = store.runtime?.robotYaw ?? 0
  let delta = normalizeAngle(targetYaw - startYaw)
  if (Math.abs(delta) < 0.01) {
    store.setRobotYaw(targetYaw)
    return
  }
  const speed = Math.max(0.25, useSimStore.getState().speed)
  const duration = (Math.abs(delta) * MS_PER_RAD) / speed
  const t0 = performance.now()
  await new Promise<void>((resolve) => {
    const tick = (now: number) => {
      if (!useSimStore.getState().running) {
        resolve()
        return
      }
      const t = Math.min(1, (now - t0) / duration)
      useSimStore.getState().setRobotYaw(startYaw + delta * t)
      if (t < 1) requestAnimationFrame(tick)
      else {
        useSimStore.getState().setRobotYaw(targetYaw)
        resolve()
      }
    }
    requestAnimationFrame(tick)
  })
}

/** Constant-speed translation between two adjacent cell centers. */
async function translateConstant(
  a: [number, number, number],
  b: [number, number, number],
): Promise<void> {
  const speed = Math.max(0.25, useSimStore.getState().speed)
  const duration = MS_PER_CELL / speed
  const t0 = performance.now()
  await new Promise<void>((resolve) => {
    const tick = (now: number) => {
      if (!useSimStore.getState().running) {
        resolve()
        return
      }
      const t = Math.min(1, (now - t0) / duration)
      const x = a[0] + (b[0] - a[0]) * t
      const z = a[2] + (b[2] - a[2]) * t
      useSimStore.getState().setRobotPosition([x, 0.35, z])
      if (t < 1) requestAnimationFrame(tick)
      else {
        useSimStore.getState().setRobotPosition([b[0], 0.35, b[2]])
        resolve()
      }
    }
    requestAnimationFrame(tick)
  })
}
