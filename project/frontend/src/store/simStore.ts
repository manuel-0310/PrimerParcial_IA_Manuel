import { create } from 'zustand'
import type { SpeechTone } from '../lib/dialogue'
import type {
  LogEntry,
  PayloadItem,
  PlanStep,
  Scenario,
  SolveResponse,
  WorldRuntime,
} from '../types'

function buildRuntime(scenario: Scenario): WorldRuntime {
  const center = scenario.layout.centers[scenario.robot.start] ?? [0, 0, 0]
  const groundKeys: Record<string, string> = {}
  for (const k of scenario.keys) groundKeys[k.id] = k.zone
  const groundTools: Record<string, string> = {}
  for (const t of scenario.tools) groundTools[t.id] = t.zone
  const groundMaterials: Record<string, { type: 'FUSE' | 'CHIP' | 'CABLE'; count: number; zone: string }> = {}
  for (const m of scenario.materials) {
    groundMaterials[m.type] = { type: m.type, count: m.count, zone: m.zone }
  }
  const doors: Record<string, 'CLOSED' | 'OPEN'> = {}
  for (const d of scenario.doors) doors[d.id] = d.state
  const panels: Record<string, 'DAMAGED' | 'OK'> = {}
  for (const p of scenario.panels) panels[p.id] = p.state
  const stations: Record<string, 'OFFLINE' | 'ONLINE'> = {}
  for (const s of scenario.stations) stations[s.id] = s.state

  return {
    robotZone: scenario.robot.start,
    battery: scenario.robot.battery_start,
    energySpent: 0,
    payload: [],
    doors,
    panels,
    stations,
    groundKeys,
    groundTools,
    groundMaterials,
    robotPosition: [center[0], 0.35, center[2]],
    robotYaw: 0,
  }
}

export interface SpeechState {
  /** Bumped on every line so the bubble can replay its pop-in animation. */
  id: number
  text: string
  tone: SpeechTone
}

/** Milliseconds the victory dance + confetti run before easing back to idle. */
export const CELEBRATION_MS = 9000

let speechTimer: ReturnType<typeof setTimeout> | null = null
let celebrationTimer: ReturnType<typeof setTimeout> | null = null
let speechCounter = 0

function clearTimers() {
  if (speechTimer !== null) clearTimeout(speechTimer)
  if (celebrationTimer !== null) clearTimeout(celebrationTimer)
  speechTimer = null
  celebrationTimer = null
}

interface SimState {
  scenario: Scenario | null
  runtime: WorldRuntime | null
  plan: PlanStep[]
  totalCost: number
  stepIndex: number
  running: boolean
  /** True while /api/solve is in flight. `running` only covers playback, so
   * without this the button stays clickable during the search. */
  solving: boolean
  log: LogEntry[]
  speed: number
  animTarget: [number, number, number] | null
  animWaypoints: [number, number, number][]
  error: string | null
  speech: SpeechState | null
  celebrating: boolean
  /** Rising counter — each increment fires one confetti burst. */
  celebrationSeed: number
  /** Rising counter — each increment fires one Mario-style pickup hop. */
  pickupSeed: number

  loadScenario: (scenario: Scenario) => void
  reset: () => void
  setPlan: (response: SolveResponse) => void
  setRunning: (v: boolean) => void
  setSolving: (v: boolean) => void
  setSpeed: (v: number) => void
  appendLog: (entry: Omit<LogEntry, 'index'>) => void
  applyRuntime: (runtime: WorldRuntime) => void
  setStepIndex: (i: number) => void
  setAnim: (waypoints: [number, number, number][], target: [number, number, number] | null) => void
  setRobotPosition: (pos: [number, number, number]) => void
  setRobotYaw: (yaw: number) => void
  setError: (msg: string | null) => void
  setPayload: (payload: PayloadItem[]) => void
  say: (text: string, tone?: SpeechTone, holdMs?: number) => void
  clearSpeech: () => void
  startCelebration: () => void
  stopCelebration: () => void
  triggerPickupHop: () => void
}

export const useSimStore = create<SimState>((set, get) => ({
  scenario: null,
  runtime: null,
  plan: [],
  totalCost: 0,
  stepIndex: 0,
  running: false,
  solving: false,
  log: [],
  speed: 1,
  animTarget: null,
  animWaypoints: [],
  error: null,
  speech: null,
  celebrating: false,
  celebrationSeed: 0,
  pickupSeed: 0,

  loadScenario: (scenario) => {
    clearTimers()
    const runtime = buildRuntime(scenario)
    set({
      scenario,
      runtime,
      plan: [],
      totalCost: 0,
      stepIndex: 0,
      running: false,
      animTarget: null,
      animWaypoints: [],
      error: null,
      speech: null,
      solving: false,
      celebrating: false,
      celebrationSeed: 0,
      pickupSeed: 0,
      log: [
        {
          index: 0,
          text: '[000] System initialized. Awaiting plan...',
          level: 'info',
        },
      ],
    })
  },

  reset: () => {
    const { scenario } = get()
    if (!scenario) return
    get().loadScenario(scenario)
  },

  setPlan: (response) => {
    set({
      plan: response.steps,
      totalCost: response.total_cost,
      stepIndex: 0,
      error: response.solution_found ? null : (response.message ?? 'FAILURE'),
    })
  },

  setRunning: (v) => set({ running: v }),
  setSolving: (v) => set({ solving: v }),
  setSpeed: (v) => set({ speed: v }),
  setStepIndex: (i) => set({ stepIndex: i }),
  setError: (msg) => set({ error: msg }),
  setPayload: (payload) => {
    const runtime = get().runtime
    if (!runtime) return
    set({ runtime: { ...runtime, payload } })
  },

  appendLog: (entry) => {
    const log = get().log
    const index = log.length
    set({ log: [...log, { ...entry, index }] })
  },

  applyRuntime: (runtime) => set({ runtime }),

  setAnim: (waypoints, target) => set({ animWaypoints: waypoints, animTarget: target }),

  setRobotPosition: (pos) => {
    const runtime = get().runtime
    if (!runtime) return
    set({ runtime: { ...runtime, robotPosition: pos } })
  },

  setRobotYaw: (yaw) => {
    const runtime = get().runtime
    if (!runtime) return
    set({ runtime: { ...runtime, robotYaw: yaw } })
  },

  say: (text, tone = 'ok', holdMs = 2600) => {
    if (speechTimer !== null) clearTimeout(speechTimer)
    speechCounter += 1
    const id = speechCounter
    set({ speech: { id, text, tone } })
    speechTimer = setTimeout(() => {
      speechTimer = null
      // Only clear if no newer line replaced this one.
      if (get().speech?.id === id) set({ speech: null })
    }, holdMs)
  },

  clearSpeech: () => {
    if (speechTimer !== null) clearTimeout(speechTimer)
    speechTimer = null
    set({ speech: null })
  },

  startCelebration: () => {
    if (celebrationTimer !== null) clearTimeout(celebrationTimer)
    set({ celebrating: true, celebrationSeed: get().celebrationSeed + 1 })
    celebrationTimer = setTimeout(() => {
      celebrationTimer = null
      set({ celebrating: false })
    }, CELEBRATION_MS)
  },

  stopCelebration: () => {
    if (celebrationTimer !== null) clearTimeout(celebrationTimer)
    celebrationTimer = null
    set({ celebrating: false })
  },

  triggerPickupHop: () => set({ pickupSeed: get().pickupSeed + 1 }),
}))

export { buildRuntime }
