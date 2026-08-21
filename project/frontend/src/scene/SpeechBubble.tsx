import { Html } from '@react-three/drei'
import { useSimStore } from '../store/simStore'

/**
 * Comic-style bubble pinned above the robot. Mounted inside the robot group,
 * so it travels with it; the Y-only offset makes it immune to the robot yaw.
 */
export function SpeechBubble() {
  const speech = useSimStore((s) => s.speech)
  if (!speech) return null

  return (
    <Html
      position={[0, 1.25, 0]}
      center
      distanceFactor={9}
      zIndexRange={[30, 0]}
      style={{ pointerEvents: 'none' }}
    >
      {/* key = id → the pop-in animation replays on every new line */}
      <div key={speech.id} className={`speech-bubble speech-${speech.tone}`}>
        {speech.text}
      </div>
    </Html>
  )
}
