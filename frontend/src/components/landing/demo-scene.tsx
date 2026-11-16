/* oxlint-disable react/immutability -- three.js scene-graph objects and
   AnimationActions returned by useGLTF/useAnimations are imperative by
   design; mutating them inside effects and useFrame is the standard
   react-three-fiber pattern, not React state. */
import { Suspense, useEffect, useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import {
  ContactShadows,
  Grid,
  Html,
  RoundedBox,
  useAnimations,
  useGLTF,
} from '@react-three/drei'
import * as THREE from 'three'

/**
 * 3D preview of the VigiTrack FSM rendered with react-three-fiber:
 * a rigged mannequin walks away from a backpack, then the alert fires.
 * The FSM state (phase) is owned by the parent demo component.
 */

type Phase = 'attended' | 'separated' | 'countdown' | 'alert'

const PERSON_START = -1.3
const PERSON_END = 2.1
const WALK_SPEED = 2.2 // units/second; crosses the 3.4-unit gap in ~1.6 s of the 2.2 s phase
const PACK_POSITION: [number, number, number] = [0.1, 0, 0.45]
// CesiumMan travels toward model +z (verified by sampling the clip: the head
// leans +z relative to the pelvis, no root motion). Rotating +90° about Y maps
// model +z → world +x, so he walks toward PERSON_END. See scripts/inspect-model.mjs.
const FACING = Math.PI / 2

/**
 * Find the frame of a walk cycle where the two feet are closest together
 * (the passing pose) — the closest thing a walk-only clip has to standing.
 * Name-agnostic: samples the clip with a scratch mixer and works out which
 * bones are the legs from their height and spread.
 */
function findIdleTime(root: THREE.Object3D, clip: THREE.AnimationClip): number {
  const SAMPLES = 48
  const fallback = clip.duration * 0.25
  const bones: THREE.Bone[] = []
  root.traverse((obj) => {
    if ((obj as THREE.Bone).isBone) bones.push(obj as THREE.Bone)
  })
  if (bones.length < 2) return fallback

  const mixer = new THREE.AnimationMixer(root)
  mixer.clipAction(clip).play()

  // positions[bone] = [x, y, z] at each sample time
  const positions: number[][][] = bones.map(() => [])
  const timeAt = (i: number) => (clip.duration * i) / SAMPLES
  const scratch = new THREE.Vector3()
  for (let i = 0; i <= SAMPLES; i++) {
    mixer.setTime(timeAt(i))
    for (let b = 0; b < bones.length; b++) {
      const p = bones[b].getWorldPosition(scratch)
      positions[b].push([p.x, p.y, p.z])
    }
  }

  // The feet are the lowest bones; among the lowest few, the pair with the
  // widest average horizontal spread is the pair of legs.
  const avgY = positions.map((ps) => ps.reduce((s, p) => s + p[1], 0) / ps.length)
  const lowest = bones
    .map((_, i) => i)
    .sort((a, b) => avgY[a] - avgY[b])
    .slice(0, 6)
  let pair: [number, number] = [lowest[0], lowest[1]]
  let widest = -1
  for (let a = 0; a < lowest.length; a++) {
    for (let b = a + 1; b < lowest.length; b++) {
      let spread = 0
      for (let i = 0; i <= SAMPLES; i++) {
        const [x1, , z1] = positions[lowest[a]][i]
        const [x2, , z2] = positions[lowest[b]][i]
        spread += Math.hypot(x1 - x2, z1 - z2)
      }
      if (spread > widest) {
        widest = spread
        pair = [lowest[a], lowest[b]]
      }
    }
  }

  // The standing frame minimises the horizontal distance between the feet.
  let bestTime = 0
  let bestDist = Infinity
  for (let i = 0; i <= SAMPLES; i++) {
    const [x1, , z1] = positions[pair[0]][i]
    const [x2, , z2] = positions[pair[1]][i]
    const d = Math.hypot(x1 - x2, z1 - z2)
    if (d < bestDist) {
      bestDist = d
      bestTime = timeAt(i)
    }
  }

  mixer.setTime(bestTime)
  mixer.stopAllAction()
  return Number.isFinite(bestTime) ? bestTime : fallback
}

function WalkingPerson({ away, reducedMotion }: { away: boolean; reducedMotion: boolean }) {
  const group = useRef<THREE.Group>(null)
  const walking = useRef(false)
  const fitted = useRef(false)
  const idleTime = useRef(0.25) // provisional; recomputed from the clip on mount
  const { scene, animations } = useGLTF('/models/CesiumMan.glb')
  const { actions } = useAnimations(animations, group)
  const firstClip = animations[0]
  const action = firstClip ? (actions[firstClip.name] ?? null) : null

  // Fit the model to a 1.8-unit height, centred, with feet on the floor.
  // Guarded so React StrictMode's double-invoke can't re-scale it.
  useEffect(() => {
    if (fitted.current) return
    fitted.current = true
    const box = new THREE.Box3().setFromObject(scene)
    const height = box.max.y - box.min.y
    if (height > 0) scene.scale.setScalar(1.8 / height)
    scene.updateMatrixWorld(true)
    const fittedBox = new THREE.Box3().setFromObject(scene)
    const centre = fittedBox.getCenter(new THREE.Vector3())
    scene.position.x -= centre.x
    scene.position.z -= centre.z
    scene.position.y -= fittedBox.min.y
  }, [scene])

  // The model has a single walk clip: play it, then park it at the frame
  // where the feet are closest together so he looks like he is standing.
  useEffect(() => {
    if (!action || !firstClip) return
    idleTime.current = findIdleTime(scene, firstClip)
    action.reset()
    action.play()
    action.paused = true
    action.time = idleTime.current
  }, [action, firstClip, scene])

  useFrame((_, delta) => {
    const g = group.current
    if (!g) return
    const targetX = away ? PERSON_END : PERSON_START

    if (reducedMotion) {
      g.position.x = targetX
      walking.current = false
      if (action) {
        action.paused = true
        action.time = idleTime.current
      }
      return
    }

    const remaining = targetX - g.position.x
    const moving = Math.abs(remaining) > 0.01
    if (moving) {
      const step = WALK_SPEED * delta
      g.position.x += Math.sign(remaining) * Math.min(step, Math.abs(remaining))
    }

    if (action) {
      if (moving) {
        action.paused = false
        walking.current = true
      } else if (walking.current) {
        action.paused = true
        action.time = idleTime.current
        walking.current = false
      }
    }
  })

  return (
    <group ref={group} position={[PERSON_START, 0, 0]} rotation={[0, FACING, 0]}>
      <primitive object={scene} />
      <Html position={[0, 2.1, 0]} center style={{ pointerEvents: 'none' }}>
        <span className="whitespace-nowrap rounded-sm bg-sky-400 px-1.5 py-px font-mono text-[10px] font-semibold text-zinc-950 shadow">
          person 0.94
        </span>
      </Html>
    </group>
  )
}

function LeftBehindPack({
  alerting,
  settling,
  reducedMotion,
}: {
  alerting: boolean
  settling: boolean
  reducedMotion: boolean
}) {
  const group = useRef<THREE.Group>(null)
  const wobble = useRef(0)

  // Settle-wobble the moment the owner walks away and leaves it behind.
  useEffect(() => {
    if (settling && !reducedMotion) wobble.current = 1
  }, [settling, reducedMotion])

  useFrame((state, delta) => {
    const g = group.current
    if (!g) return
    if (wobble.current > 0.003) {
      wobble.current = THREE.MathUtils.damp(wobble.current, 0, 2.4, delta)
      g.rotation.z = Math.sin(state.clock.elapsedTime * 15) * 0.13 * wobble.current
    } else if (g.rotation.z !== 0) {
      g.rotation.z = 0
    }
  })

  return (
    <group ref={group} position={PACK_POSITION}>
      {/* body */}
      <RoundedBox args={[0.62, 0.66, 0.34]} radius={0.08} smoothness={4} position={[0, 0.34, 0]}>
        <meshStandardMaterial
          color={alerting ? '#ef4444' : '#f59e0b'}
          roughness={0.5}
          metalness={0.05}
          emissive={alerting ? '#7f1d1d' : '#000000'}
          emissiveIntensity={alerting ? 0.9 : 0}
        />
      </RoundedBox>
      {/* front pocket */}
      <RoundedBox args={[0.36, 0.26, 0.1]} radius={0.04} smoothness={4} position={[0, 0.24, 0.19]}>
        <meshStandardMaterial
          color={alerting ? '#dc2626' : '#d97706'}
          roughness={0.55}
        />
      </RoundedBox>
      {/* carry handle */}
      <mesh position={[0, 0.68, 0]}>
        <torusGeometry args={[0.13, 0.028, 10, 28, Math.PI]} />
        <meshStandardMaterial
          color={alerting ? '#b91c1c' : '#b45309'}
          roughness={0.5}
        />
      </mesh>
      <Html position={[0, 1.0, 0]} center style={{ pointerEvents: 'none' }}>
        <span
          className={`whitespace-nowrap rounded-sm px-1.5 py-px font-mono text-[10px] font-semibold shadow ${
            alerting ? 'bg-red-500 text-white' : 'bg-amber-400 text-zinc-950'
          }`}
        >
          backpack 0.87
        </span>
      </Html>
    </group>
  )
}

function Floor() {
  return (
    <>
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[60, 60]} />
        <meshStandardMaterial color="#191920" roughness={1} />
      </mesh>
      <Grid
        position={[0, 0.005, 0]}
        cellSize={0.55}
        cellThickness={0.7}
        cellColor="#26262e"
        sectionSize={2.2}
        sectionThickness={1}
        sectionColor="#3b3b46"
        fadeDistance={26}
        fadeStrength={1.5}
        infiniteGrid
      />
    </>
  )
}

export default function DemoScene({
  phase,
  reducedMotion,
}: {
  phase: Phase
  reducedMotion: boolean
}) {
  const away = phase !== 'attended'
  const alerting = phase === 'alert'
  const settling = phase === 'separated'

  return (
    <div className="absolute inset-0">
      <Canvas
        dpr={[1, 2]}
        camera={{ position: [1.1, 3.5, 6.6], fov: 36 }}
        gl={{ antialias: true }}
        onCreated={({ camera }) => camera.lookAt(0.4, 0.95, 0)}
      >
        <color attach="background" args={['#0c0c0f']} />
        <fog attach="fog" args={['#0c0c0f', 12, 28]} />
        <ambientLight intensity={0.6} />
        <directionalLight position={[4, 7, 3]} intensity={1.5} />
        <directionalLight position={[-5, 4, -3]} intensity={0.5} color="#7dd3fc" />
        {alerting && (
          <pointLight
            position={[0.4, 2.2, 1.4]}
            intensity={20}
            color="#ef4444"
            distance={16}
            decay={2}
          />
        )}
        <Floor />
        <ContactShadows
          position={[0, 0.02, 0]}
          opacity={0.6}
          scale={16}
          blur={2.4}
          far={5}
          resolution={512}
          frames={Infinity}
        />
        <Suspense fallback={null}>
          <WalkingPerson away={away} reducedMotion={reducedMotion} />
          <LeftBehindPack
            alerting={alerting}
            settling={settling}
            reducedMotion={reducedMotion}
          />
        </Suspense>
      </Canvas>
    </div>
  )
}
