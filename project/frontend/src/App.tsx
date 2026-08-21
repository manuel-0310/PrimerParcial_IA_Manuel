import { useEffect, useRef } from 'react'
import { Canvas } from '@react-three/fiber'
import scenarioData from '@scenario'
import type { Scenario } from './types'
import { useSimStore } from './store/simStore'
import { World } from './scene/World'
import {
  BottomControls,
  CelebrationOverlay,
  LeftPanel,
  RightPanel,
  SolvingOverlay,
} from './ui/HUD'
import { fetchPlan, runPlan } from './lib/api'
import './App.css'

const scenario = scenarioData as Scenario

export default function App() {
  const loadScenario = useSimStore((s) => s.loadScenario)
  const reset = useSimStore((s) => s.reset)
  const setPlan = useSimStore((s) => s.setPlan)
  const appendLog = useSimStore((s) => s.appendLog)
  const setError = useSimStore((s) => s.setError)
  const setSolving = useSimStore((s) => s.setSolving)
  const say = useSimStore((s) => s.say)
  const clearSpeech = useSimStore((s) => s.clearSpeech)
  const busy = useRef(false)
  const inFlight = useRef<AbortController | null>(null)

  // Sin abortar, un RESET durante la búsqueda deja la petición viva y el plan
  // arranca solo minutos después.
  const onReset = () => {
    inFlight.current?.abort()
    inFlight.current = null
    busy.current = false
    reset()
  }

  useEffect(() => {
    loadScenario(scenario)
  }, [loadScenario])

  const onExecute = async () => {
    // Dos planes a la vez se pisan sobre el mismo mundo. El ref cubre además
    // el hueco entre el fetch y runPlan(), donde solving y running son false.
    if (busy.current) return
    busy.current = true

    try {
      setError(null)
      reset()
      appendLog({
        text: '[---] Requesting plan from /api/solve (UCS puede tardar varios minutos)...',
        level: 'info',
      })
      // Solo la espera del backend; el overlay se quita antes de reproducir.
      setSolving(true)
      say('Déjame pensar... 🤔', 'info', 900_000)
      const controller = new AbortController()
      inFlight.current = controller
      let response
      try {
        response = await fetchPlan(scenario, controller.signal)
      } finally {
        inFlight.current = null
        setSolving(false)
        clearSpeech()
      }
      setPlan(response)
      if (!response.solution_found) {
        appendLog({
          text: `[---] FAILURE: ${response.message ?? 'no solution'}`,
          level: 'error',
        })
        return
      }
      appendLog({
        text: `[---] Plan received — ${response.steps.length} steps, cost ${response.total_cost}`,
        level: 'ok',
      })
      // Deja asentar el reset antes de reproducir.
      await new Promise((r) => setTimeout(r, 200))
      await runPlan()
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        appendLog({ text: '[---] Búsqueda cancelada.', level: 'warn' })
        return
      }
      const msg = err instanceof Error ? err.message : String(err)
      setError(msg)
      appendLog({ text: `[---] API ERROR: ${msg}`, level: 'error' })
      say('¡Ups! No consigo hablar con el servidor 😵', 'warn', 6000)
    } finally {
      busy.current = false
    }
  }

  return (
    <div className="app-shell">
      <div className="viewport">
        <Canvas
          shadows="soft"
          camera={{ position: [16, 14, 18], fov: 42, near: 0.1, far: 200 }}
        >
          <World />
        </Canvas>
      </div>
      <LeftPanel />
      <RightPanel />
      <BottomControls onExecute={onExecute} onReset={onReset} />
      <SolvingOverlay />
      <CelebrationOverlay />
    </div>
  )
}
