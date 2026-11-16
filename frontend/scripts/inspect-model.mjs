import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { AnimationMixer, Vector3 } from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'

// Minimal browser globals so GLTFLoader runs headless.
globalThis.self = globalThis

const here = dirname(fileURLToPath(import.meta.url))
const glbPath = join(here, '..', 'public', 'models', 'CesiumMan.glb')
const buf = readFileSync(glbPath)

// Peek at the GLB JSON chunk first (works even if GLTFLoader chokes).
const jsonLen = buf.readUInt32LE(12)
const gltfJson = JSON.parse(buf.subarray(20, 20 + jsonLen).toString('utf8'))
console.log('images in GLB:', (gltfJson.images ?? []).length)
console.log('animations in JSON:', (gltfJson.animations ?? []).length)

const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength)
new GLTFLoader().parse(
  ab,
  '',
  (gltf) => main(gltf),
  (err) => {
    console.error('GLTFLoader PARSE FAILED:', err?.message ?? err)
    process.exit(1)
  },
)

function main(gltf) {
  const { scene, animations } = gltf
  const clip = animations[0]
  console.log('clip name:', JSON.stringify(clip.name), '| duration:', clip.duration.toFixed(3))

  const bones = []
  scene.traverse((o) => {
    if (o.isBone) bones.push(o)
  })
  console.log('bones (' + bones.length + '):')
  console.log('  ' + bones.map((b) => b.name).join(', '))

  const mixer = new AnimationMixer(scene)
  const action = mixer.clipAction(clip)
  action.play()

  const N = 48
  const timeAt = (i) => (clip.duration * i) / N
  const times = []
  const frames = [] // frames[i][bone] = [x, y, z]
  for (let i = 0; i <= N; i++) {
    const t = (clip.duration * i) / N
    mixer.setTime(t)
    scene.updateMatrixWorld(true)
    times.push(action.time)
    frames.push(
      bones.map((b) => {
        const p = new Vector3()
        b.getWorldPosition(p)
        return [p.x, p.y, p.z]
      }),
    )
  }
  console.log(
    'action.time after setTime (first 6):',
    times.slice(0, 6).map((x) => x.toFixed(3)).join(', '),
  )

  // avg height per bone -> head is highest, feet lowest
  const avgY = bones.map((_, bi) => frames.reduce((s, f) => s + f[bi][1], 0) / (N + 1))
  const byHeight = bones.map((_, i) => i).sort((a, b) => avgY[b] - avgY[a])
  console.log('avgY (high to low):')
  console.log('  ' + byHeight.map((i) => `${bones[i].name}=${avgY[i].toFixed(3)}`).join(', '))

  // Reproduce findIdleTime: lowest 6 bones, widest horizontal pair = legs.
  const lowest = [...byHeight].reverse().slice(0, 6)
  let pair = [lowest[0], lowest[1]]
  let widest = -1
  for (let a = 0; a < lowest.length; a++) {
    for (let b = a + 1; b < lowest.length; b++) {
      let spread = 0
      for (let i = 0; i <= N; i++) {
        const p1 = frames[i][lowest[a]]
        const p2 = frames[i][lowest[b]]
        spread += Math.hypot(p1[0] - p2[0], p1[2] - p2[2])
      }
      if (spread > widest) {
        widest = spread
        pair = [lowest[a], lowest[b]]
      }
    }
  }
  console.log('chosen leg pair:', pair.map((i) => bones[i].name).join(' vs '))
  console.log('avg horizontal spread:', (widest / (N + 1)).toFixed(3))

  // Distance between the legs at each sample.
  const dists = []
  let best = 0
  let bestD = Infinity
  let maxD = 0
  for (let i = 0; i <= N; i++) {
    const p1 = frames[i][pair[0]]
    const p2 = frames[i][pair[1]]
    const d = Math.hypot(p1[0] - p2[0], p1[2] - p2[2])
    dists.push(d)
    if (d < bestD) {
      bestD = d
      best = i
    }
    if (d > maxD) maxD = d
  }
  console.log(
    `leg XZ distance: min=${bestD.toFixed(3)} at frame ${best}/${N} (t=${(
      (clip.duration * best) /
      N
    ).toFixed(3)}s), max=${maxD.toFixed(3)}`,
  )
  console.log('distance per frame:', dists.map((d) => d.toFixed(2)).join(' '))
  console.log('distance at t=0:', dists[0].toFixed(3), '| at t=25%:', dists[12].toFixed(3))

  // Stride axis = direction the legs separate along.
  let minX = Infinity
  let maxX = -Infinity
  let minZ = Infinity
  let maxZ = -Infinity
  for (let i = 0; i <= N; i++) {
    const p = frames[i][pair[0]]
    minX = Math.min(minX, p[0])
    maxX = Math.max(maxX, p[0])
    minZ = Math.min(minZ, p[2])
    maxZ = Math.max(maxZ, p[2])
  }
  const axis = maxX - minX >= maxZ - minZ ? 'x' : 'z'
  console.log(
    `stride axis: ${axis} (leg range x=${(maxX - minX).toFixed(2)}, z=${(maxZ - minZ).toFixed(2)})`,
  )

  // Facing: the torso leans in the direction of travel; also check for
  // root motion (pelvis translating across the clip).
  const headI = byHeight[0]
  // This rig has no "hips"-named bone: the pelvis is the common parent of
  // the two upper leg bones.
  const upperLegs = bones.filter((b) => /leg_joint_[LR]_1$/.test(b.name))
  const pelvis =
    upperLegs.length === 2 && upperLegs[0].parent === upperLegs[1].parent
      ? upperLegs[0].parent
      : null
  console.log(
    'head bone:',
    bones[headI].name,
    '| pelvis:',
    pelvis ? `${pelvis.name} (isBone=${!!pelvis.isBone})` : 'NOT FOUND',
  )
  console.log(
    'node hierarchy:',
    (() => {
      const lines = []
      scene.traverse((o) => {
        const depth = (() => {
          let d = 0
          let p = o.parent
          while (p) {
            d++
            p = p.parent
          }
          return d
        })()
        lines.push('  '.repeat(depth) + o.name + (o.isBone ? ' [bone]' : ''))
      })
      return '\n' + lines.join('\n')
    })(),
  )

  if (pelvis) {
    // Pelvis world positions: reuse the sampled frames when the pelvis is
    // itself a Bone (true for this rig), otherwise sample it directly.
    const pelvisI = bones.indexOf(pelvis)
    const pelvisFrames = []
    if (pelvisI >= 0) {
      for (let i = 0; i <= N; i++) pelvisFrames.push(frames[i][pelvisI])
    } else {
      for (let i = 0; i <= N; i++) {
        mixer.setTime(timeAt(i))
        scene.updateMatrixWorld(true)
        const p = new Vector3()
        pelvis.getWorldPosition(p)
        pelvisFrames.push([p.x, p.y, p.z])
      }
    }
    let leanSum = 0
    for (let i = 0; i <= N; i++) {
      const h = frames[i][headI]
      const hp = pelvisFrames[i]
      leanSum += axis === 'x' ? h[0] - hp[0] : h[2] - hp[2]
    }
    const lean = leanSum / (N + 1)
    console.log(
      `avg (head - pelvis) along stride axis: ${lean.toFixed(4)} -> travel direction: ${lean > 0 ? '+' : '-'}${axis}`,
    )
    const f0 = pelvisFrames[0]
    const fN = pelvisFrames[N]
    console.log(
      `pelvis net displacement over clip: dx=${(fN[0] - f0[0]).toFixed(3)}, dz=${(fN[2] - f0[2]).toFixed(3)}`,
    )
    // Recommended FACING so travel maps to world +x.
    const dir = lean > 0 ? `+${axis}` : `-${axis}`
    const facing =
      dir === '+z' ? Math.PI / 2 : dir === '-z' ? -Math.PI / 2 : dir === '+x' ? 0 : Math.PI
    console.log('recommended FACING constant:', facing.toFixed(4), `(${(facing * 180) / Math.PI} deg)`)
  }
}
