import { Bloom, EffectComposer } from '@react-three/postprocessing'
import { HalfFloatType } from 'three'

/**
 * Bloom that only catches the neon bits on an otherwise bright scene.
 *
 * The buffer is HDR (HalfFloat) and normal surfaces are tone mapped in-shader,
 * landing below 1.0. Only `toneMapped={false}` materials with emissive above 1
 * cross the threshold, so the white floor stays white.
 */
export function Effects() {
  return (
    <EffectComposer frameBufferType={HalfFloatType} multisampling={4}>
      <Bloom
        mipmapBlur
        luminanceThreshold={1.0}
        luminanceSmoothing={0.2}
        intensity={0.9}
        radius={0.75}
      />
    </EffectComposer>
  )
}
