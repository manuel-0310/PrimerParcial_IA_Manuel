import type { PlanStep, Scenario, WorldRuntime } from '../types'

export type SpeechTone = 'info' | 'ok' | 'warn' | 'celebrate'

export interface SpeechLine {
  text: string
  tone: SpeechTone
  /** Milliseconds the bubble stays on screen. */
  hold: number
}

interface Candidate extends SpeechLine {
  /** Dedupe key — a non-milestone line is only ever said once per run. */
  key: string
  /** Milestones always speak, even if another line just fired. */
  milestone: boolean
}

/** Plan steps that must pass between two non-milestone lines. */
const MIN_STEP_GAP = 5
/** Minimum gap between milestones, so bubbles can be read. */
const MILESTONE_MIN_GAP = 2

const COLOR_ES: Record<string, string> = {
  cyan: 'cian',
  yellow: 'amarilla',
  magenta: 'magenta',
  green: 'verde',
  red: 'roja',
  blue: 'azul',
  orange: 'naranja',
}

const MATERIAL_ES: Record<string, string> = {
  FUSE: 'fusible',
  CHIP: 'chip',
  CABLE: 'cable',
}

function pick(options: string[]): string {
  return options[Math.floor(Math.random() * options.length)]
}

/** Fires only when crossing the threshold, not on every MOVE. */
const LOW_BATTERY = 0.3
const CRITICAL_BATTERY = 0.15

function batteryCandidate(
  scenario: Scenario,
  before: WorldRuntime,
  after: WorldRuntime,
): Candidate | null {
  const max = scenario.robot.battery_max
  const wasPct = before.battery / max
  const nowPct = after.battery / max
  if (wasPct >= CRITICAL_BATTERY && nowPct < CRITICAL_BATTERY) {
    return {
      text: `Batería crítica: ${after.battery} 🪫 ¡Voy a gatas!`,
      tone: 'warn',
      hold: 3200,
      key: 'battery:critical',
      milestone: true,
    }
  }
  if (wasPct >= LOW_BATTERY && nowPct < LOW_BATTERY) {
    return {
      text: `Uf... batería al ${Math.round(nowPct * 100)}% 🔋`,
      tone: 'warn',
      hold: 3000,
      key: 'battery:low',
      milestone: true,
    }
  }
  return null
}

function pickupCandidate(scenario: Scenario, itemId: string): Candidate {
  const key = scenario.keys.find((k) => k.id === itemId)
  if (key) {
    const color = COLOR_ES[key.color] ?? key.color
    return {
      text: pick([
        `¡Recogí la llave ${color}! 🔑`,
        `Llave ${color} en el bolsillo. Esa puerta ya no me para. 🔑`,
      ]),
      tone: 'ok',
      hold: 2600,
      key: 'pickup:key',
      milestone: false,
    }
  }

  const tool = scenario.tools.find((t) => t.id === itemId)
  if (tool) {
    return {
      text: pick([
        `¡Recogí ${itemId}! 🛠️`,
        `Con ${itemId} arreglo lo ${tool.repairs.toLowerCase()}. 🛠️`,
      ]),
      tone: 'ok',
      hold: 2600,
      key: 'pickup:tool',
      milestone: false,
    }
  }

  const material = MATERIAL_ES[itemId]
  if (material) {
    return {
      text: pick([`¡Recogí un ${material}! 📦`, `Un ${material} para la mochila. 📦`]),
      tone: 'ok',
      hold: 2400,
      key: 'pickup:material',
      milestone: false,
    }
  }

  return { text: `¡Recogí ${itemId}!`, tone: 'ok', hold: 2400, key: 'pickup:other', milestone: false }
}

function candidateFor(
  scenario: Scenario,
  step: PlanStep,
  before: WorldRuntime,
  after: WorldRuntime,
): Candidate | null {
  if (step.op === 'PICKUP' && step.item) return pickupCandidate(scenario, step.item)

  if (step.op === 'DROP' && step.item) {
    return {
      text: pick([
        `Suelto ${step.item} aquí, ya vuelvo. 👋`,
        `No me cabe todo... adiós ${step.item}. 👋`,
      ]),
      tone: 'info',
      hold: 2600,
      key: 'drop',
      milestone: false,
    }
  }

  if (step.op === 'MOVE') return batteryCandidate(scenario, before, after)

  if (step.op === 'INTERACT') {
    const target = step.target ?? ''
    switch (step.action) {
      case 'OPEN_DOOR':
        return {
          text: pick([`¡${target} abierta! 🚪`, `Clic... ¡y se abrió! 🚪`]),
          tone: 'ok',
          hold: 2400,
          key: 'door',
          milestone: false,
        }
      case 'REPAIR':
        return {
          text: pick([`¡${target} reparado! 🔧`, `Panel ${target} como nuevo. ✅`]),
          tone: 'ok',
          hold: 2600,
          key: 'repair',
          milestone: false,
        }
      // Every station coming online is a milestone.
      case 'ACTIVATE':
        return {
          text: pick([`¡${target} ONLINE! ⚡`, `${target} encendida. ¡Vamos! ⚡`]),
          tone: 'celebrate',
          hold: 3000,
          key: `activate:${target}`,
          milestone: true,
        }
      case 'RECHARGE':
        return {
          text: pick([`Ahhh... recarga completa. 🔋`, `¡Batería al 100%! Como nuevo. 🔋`]),
          tone: 'ok',
          hold: 2600,
          key: 'recharge',
          milestone: false,
        }
      default:
        return null
    }
  }

  return null
}

/**
 * Picks which lines reach the bubble: milestones always, the rest at most once
 * per run and never back to back.
 */
export function createSpeechDirector() {
  const said = new Set<string>()
  let lastSpokenStep = -MIN_STEP_GAP

  return {
    lineFor(
      scenario: Scenario,
      step: PlanStep,
      before: WorldRuntime,
      after: WorldRuntime,
      stepIndex: number,
    ): SpeechLine | null {
      const candidate = candidateFor(scenario, step, before, after)
      if (!candidate) return null

      const gap = stepIndex - lastSpokenStep
      if (candidate.milestone) {
        if (gap < MILESTONE_MIN_GAP) return null
      } else {
        if (said.has(candidate.key)) return null
        if (gap < MIN_STEP_GAP) return null
      }

      said.add(candidate.key)
      lastSpokenStep = stepIndex
      return { text: candidate.text, tone: candidate.tone, hold: candidate.hold }
    },
  }
}

export function successLine(): SpeechLine {
  return {
    text: '¡Misión cumplida! 🎉 ¿Alguien dijo fiesta?',
    tone: 'celebrate',
    hold: 9000,
  }
}

export function incompleteLine(): SpeechLine {
  return {
    text: 'Terminé el plan... pero falta alguna estación. 🤔',
    tone: 'warn',
    hold: 5000,
  }
}

export function failureLine(message: string): SpeechLine {
  const short = message.length > 70 ? `${message.slice(0, 67)}...` : message
  return { text: `¡Ups! No puedo seguir: ${short} 😵`, tone: 'warn', hold: 6000 }
}
