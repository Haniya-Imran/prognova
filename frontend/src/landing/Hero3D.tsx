import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { RoundedBox, Sparkles, Stars } from '@react-three/drei'
import { useMemo, useRef } from 'react'
import * as THREE from 'three'

// Heights are the real monthly net revenue of the demo dataset (Dec 2009 – Nov 2011),
// scaled to the largest value; the three amber towers are the model's real forecast
// for Dec 2011 – Feb 2012, with a ghost column for the top of the 80% range.
const HISTORY = [0.545, 0.424, 0.368, 0.527, 0.446, 0.425, 0.47, 0.432, 0.464, 0.59, 0.749, 0.977, 0.812, 0.406, 0.35, 0.476, 0.338, 0.512, 0.507, 0.474, 0.491, 0.709, 0.744, 1.0]
const FORECAST = [{ v: 0.812, hi: 0.975 }, { v: 0.406, hi: 0.485 }, { v: 0.35, hi: 0.404 }]
const H = 4.2
const STEP = 0.46

function Tower({ x, h, color, glow, delay, ghost }: { x: number; h: number; color: string; glow: number; delay: number; ghost?: number }) {
  const g = useRef<THREE.Group>(null)
  useFrame((s) => {
    const t = Math.min(Math.max((s.clock.elapsedTime - delay) / 1.1, 0), 1)
    const e = 1 - Math.pow(1 - t, 3)
    if (g.current) g.current.scale.y = Math.max(0.001, e)
  })
  return (
    <group position={[x, 0, 0]}>
      <group ref={g}>
        <RoundedBox args={[0.34, h, 0.34]} radius={0.05} smoothness={3} position={[0, h / 2, 0]}>
          <meshStandardMaterial color={color} emissive={color} emissiveIntensity={glow} metalness={0.35} roughness={0.25} />
        </RoundedBox>
        {/* window lights */}
        {Array.from({ length: Math.floor(h / 0.32) }).map((_, i) => (
          <mesh key={i} position={[0, 0.2 + i * 0.32, 0.172]}>
            <planeGeometry args={[0.2, 0.05]} />
            <meshBasicMaterial color="#e9fffb" transparent opacity={0.22 + ((i * 7) % 5) * 0.08} />
          </mesh>
        ))}
      </group>
      {ghost && (
        <mesh position={[0, ghost / 2, 0]}>
          <boxGeometry args={[0.42, ghost, 0.42]} />
          <meshBasicMaterial color={color} transparent opacity={0.08} depthWrite={false} />
        </mesh>
      )}
    </group>
  )
}

function Skyline() {
  const group = useRef<THREE.Group>(null)
  const { pointer } = useThree()
  useFrame((s, dt) => {
    if (!group.current) return
    const targetY = -0.5 + pointer.x * 0.2 + Math.sin(s.clock.elapsedTime * 0.15) * 0.06
    const targetX = 0.06 - pointer.y * 0.06
    group.current.rotation.y += (targetY - group.current.rotation.y) * Math.min(dt * 2, 1)
    group.current.rotation.x += (targetX - group.current.rotation.x) * Math.min(dt * 2, 1)
  })
  const n = HISTORY.length + FORECAST.length
  const x0 = -((n - 1) * STEP) / 2
  const curve = useMemo(() => {
    const pts = [...HISTORY.slice(-6), ...FORECAST.map((f) => f.v)].map((v, i) => new THREE.Vector3(x0 + (HISTORY.length - 6 + i) * STEP, v * H + 0.25, 0))
    return new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 120, 0.025, 8, false)
  }, [x0])
  return (
    <group ref={group} position={[1.7, -2.3, -1]} scale={0.72}>
      {HISTORY.map((v, i) => (
        <Tower key={i} x={x0 + i * STEP} h={v * H} color={i % 12 === 10 || i % 12 === 11 ? '#3ff0d2' : '#1fb7a0'} glow={0.28} delay={0.15 + i * 0.035} />
      ))}
      {FORECAST.map((f, i) => (
        <Tower key={`f${i}`} x={x0 + (HISTORY.length + i) * STEP} h={f.v * H} ghost={f.hi * H} color="#ffb547" glow={0.65} delay={1.2 + i * 0.12} />
      ))}
      <mesh geometry={curve}><meshBasicMaterial color="#ffd38a" /></mesh>
      {/* glowing floor grid */}
      <gridHelper args={[26, 52, '#2ee6c8', '#1a2a4d']} position={[0, 0.001, 0]} />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]}>
        <circleGeometry args={[9, 64]} />
        <meshBasicMaterial color="#2ee6c8" transparent opacity={0.05} />
      </mesh>
    </group>
  )
}

function Nova() {
  const ref = useRef<THREE.Group>(null)
  useFrame((s) => {
    const t = s.clock.elapsedTime * 0.35
    if (ref.current) ref.current.position.set(Math.cos(t) * 5.2 + 2.6, 2.6 + Math.sin(t * 2) * 0.25, Math.sin(t) * 2.2 - 2)
  })
  return (
    <group ref={ref}>
      <mesh><sphereGeometry args={[0.12, 24, 24]} /><meshBasicMaterial color="#fff3d6" /></mesh>
      <pointLight color="#ffb547" intensity={14} distance={9} />
    </group>
  )
}

export default function Hero3D() {
  return (
    <Canvas camera={{ position: [0, 1.8, 12.5], fov: 40 }} dpr={[1, 1.75]} gl={{ antialias: true, alpha: true }} aria-hidden>
      <fog attach="fog" args={['#1c2847', 11, 26]} />
      <ambientLight intensity={0.45} />
      <directionalLight position={[6, 9, 6]} intensity={1.2} color="#cfe9ff" />
      <directionalLight position={[-8, 3, -4]} intensity={0.8} color="#8f7bff" />
      <Stars radius={60} depth={30} count={2200} factor={3} saturation={0} fade speed={0.6} />
      <Sparkles count={60} scale={[16, 6, 6]} position={[0, 1, 0]} size={2.2} speed={0.3} color="#2ee6c8" opacity={0.6} />
      <Skyline />
      <Nova />
    </Canvas>
  )
}
