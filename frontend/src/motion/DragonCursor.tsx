import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { gsap } from 'gsap'
import { useDragonCursorSetting } from '../settings'
import { prefersReducedMotion } from './ScrollMotion'

const SEGMENTS = 44
const SPACING = 8
const INTERACTIVE = 'a, button, select, label, input, textarea, [role="switch"], [role="button"], .row-action'

type Ember = { x: number; y: number; vx: number; vy: number; life: number; max: number; size: number }
type Palette = { tail: [number, number, number]; head: [number, number, number]; spike: string; eye: string; glow: string }

const PALETTES: Record<'light' | 'dark', Palette> = {
  light: { tail: [104, 44, 12], head: [238, 112, 36], spike: '#f2b33d', eye: '#ffe08a', glow: '238, 112, 36' },
  dark: { tail: [128, 34, 14], head: [255, 150, 70], spike: '#ffd08a', eye: '#fff3c4', glow: '255, 138, 61' },
}

const mix = (a: [number, number, number], b: [number, number, number], t: number) =>
  `rgb(${Math.round(a[0] + (b[0] - a[0]) * t)}, ${Math.round(a[1] + (b[1] - a[1]) * t)}, ${Math.round(a[2] + (b[2] - a[2]) * t)})`

export function DragonCursor() {
  const ref = useRef<HTMLCanvasElement>(null)
  const { enabled } = useDragonCursorSetting()
  useEffect(() => {
    const canvas = ref.current
    if (!enabled || !canvas || prefersReducedMotion() || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return
    const c = canvas.getContext('2d')
    if (!c) return
    const root = document.documentElement
    root.classList.add('dragon-cursor')

    let w = 0
    let h = 0
    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      w = window.innerWidth
      h = window.innerHeight
      canvas.width = w * dpr
      canvas.height = h * dpr
      canvas.style.width = `${w}px`
      canvas.style.height = `${h}px`
      c.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    resize()

    const pts = Array.from({ length: SEGMENTS }, () => ({ x: 0, y: 0 }))
    const mouse = { x: 0, y: 0, seen: false }
    const embers: Ember[] = []
    let heading = 0
    let speed = 0
    let hover = false
    let pulse = 0
    let alpha = 0
    let alphaTarget = 1

    const burst = (x: number, y: number, count: number, power: number) => {
      for (let i = 0; i < count; i += 1) {
        const angle = Math.random() * Math.PI * 2
        const v = (0.4 + Math.random()) * power
        embers.push({ x, y, vx: Math.cos(angle) * v, vy: Math.sin(angle) * v - 0.4, life: 0, max: 30 + Math.random() * 30, size: 1 + Math.random() * 2.2 })
      }
    }
    const onMove = (event: PointerEvent) => {
      mouse.x = event.clientX
      mouse.y = event.clientY
      if (!mouse.seen) {
        mouse.seen = true
        pts.forEach((p) => { p.x = mouse.x; p.y = mouse.y })
      }
      alphaTarget = 1
      hover = Boolean((event.target as HTMLElement | null)?.closest?.(INTERACTIVE))
    }
    const onDown = () => { pulse = 1; burst(pts[0].x, pts[0].y, 22, 3.2) }
    const onLeave = () => { alphaTarget = 0 }
    window.addEventListener('pointermove', onMove, { passive: true })
    window.addEventListener('pointerdown', onDown, { passive: true })
    window.addEventListener('resize', resize)
    root.addEventListener('pointerleave', onLeave)

    const tick = () => {
      alpha += (alphaTarget - alpha) * 0.12
      c.clearRect(0, 0, w, h)
      if (!mouse.seen || alpha < 0.02) return
      const theme = root.dataset.theme === 'dark' ? 'dark' : 'light'
      const pal = PALETTES[theme]

      const head = pts[0]
      const dx = mouse.x - head.x
      const dy = mouse.y - head.y
      const dist = Math.hypot(dx, dy)
      head.x += dx * 0.4
      head.y += dy * 0.4
      speed += (Math.min(dist, 60) - speed) * 0.2
      if (dist > 1.2) {
        let diff = Math.atan2(dy, dx) - heading
        diff = Math.atan2(Math.sin(diff), Math.cos(diff))
        heading += diff * 0.3
      }
      pulse *= 0.92
      for (let i = 1; i < SEGMENTS; i += 1) {
        const prev = pts[i - 1]
        const p = pts[i]
        const ax = p.x - prev.x
        const ay = p.y - prev.y
        const d = Math.hypot(ax, ay) || 1
        const k = SPACING / d
        p.x = prev.x + ax * k
        p.y = prev.y + ay * k
      }

      const body = pts.map((p, i) => {
        const a = pts[Math.max(i - 1, 0)]
        const b = pts[Math.min(i + 1, SEGMENTS - 1)]
        const tx = b.x - a.x
        const ty = b.y - a.y
        const len = Math.hypot(tx, ty) || 1
        return { x: p.x, y: p.y, nx: -ty / len, ny: tx / len }
      })

      c.save()
      c.globalAlpha = alpha

      // dorsal spikes, then body
      for (let i = SEGMENTS - 2; i >= 3; i -= 1) {
        if (i % 2) continue
        const t = 1 - i / SEGMENTS
        const r = 1.4 + Math.pow(t, 0.75) * 10.5
        const s = r * 1.1 + 3
        const { x, y, nx, ny } = body[i]
        const bx = body[i - 1].x - body[i + 1].x
        const by = body[i - 1].y - body[i + 1].y
        c.fillStyle = pal.spike
        c.beginPath()
        c.moveTo(x + nx * r, y + ny * r)
        c.lineTo(x + nx * (r + s) + bx * 0.35, y + ny * (r + s) + by * 0.35)
        c.lineTo(x + nx * r - bx * 0.15, y + ny * r - by * 0.15)
        c.fill()
      }
      for (let i = SEGMENTS - 1; i >= 1; i -= 1) {
        const t = 1 - i / SEGMENTS
        const r = 1.4 + Math.pow(t, 0.75) * 10.5
        c.fillStyle = mix(pal.tail, pal.head, t)
        c.beginPath()
        c.arc(body[i].x, body[i].y, r, 0, Math.PI * 2)
        c.fill()
        if (i % 3 === 0) {
          c.strokeStyle = `rgba(255, 220, 160, ${0.28 * t})`
          c.lineWidth = 1
          c.beginPath()
          c.arc(body[i].x, body[i].y, r * 0.72, Math.PI * 1.05, Math.PI * 1.9)
          c.stroke()
        }
      }

      // head
      const grow = 1.4 + (hover ? 0.3 : 0) + pulse * 0.45
      c.save()
      c.translate(body[0].x, body[0].y)
      c.rotate(heading)
      c.scale(grow, grow)
      const wob = 0
      c.strokeStyle = pal.spike
      c.lineWidth = 2.4
      c.lineCap = 'round'
      for (const side of [-1, 1]) {
        c.beginPath()
        c.moveTo(-1, side * 5)
        c.quadraticCurveTo(-12, side * 15, -26, side * (11 + wob * 2))
        c.stroke()
        c.lineWidth = 0.9
        c.beginPath()
        c.moveTo(9, side * 3)
        c.bezierCurveTo(18, side * (8 + wob * 2), 24, side * 5, 31 + wob * 2, side * (11 + wob * 3))
        c.stroke()
        c.lineWidth = 2.4
      }
      c.fillStyle = mix(pal.tail, pal.head, 1)
      c.beginPath()
      c.ellipse(0, 0, 11.5, 8.5, 0, 0, Math.PI * 2)
      c.fill()
      c.beginPath()
      c.ellipse(9, 0, 8, 5.2, 0, 0, Math.PI * 2)
      c.fill()
      c.fillStyle = pal.spike
      c.beginPath()
      c.moveTo(-8, 0)
      c.lineTo(-14, -3)
      c.lineTo(-12, 0)
      c.lineTo(-14, 3)
      c.fill()
      c.fillStyle = pal.eye
      for (const side of [-1, 1]) {
        c.beginPath()
        c.ellipse(3.5, side * 4.2, 2.3, 1.4, side * -0.4, 0, Math.PI * 2)
        c.fill()
      }
      c.fillStyle = 'rgba(30, 8, 4, 0.8)'
      for (const side of [-1, 1]) {
        c.beginPath()
        c.arc(14, side * 1.8, 0.9, 0, Math.PI * 2)
        c.fill()
      }
      c.restore()

      if (hover || pulse > 0.05) {
        c.strokeStyle = `rgba(${pal.glow}, ${0.55 * (hover ? 1 : pulse)})`
        c.lineWidth = 1.5
        c.beginPath()
        c.arc(body[0].x, body[0].y, 20 + pulse * 14, 0, Math.PI * 2)
        c.stroke()
      }

      // embers
      if (speed > 7 && Math.random() < 0.55) burst(body[3].x, body[3].y, 1, 0.9)
      c.globalCompositeOperation = 'lighter'
      for (let i = embers.length - 1; i >= 0; i -= 1) {
        const e = embers[i]
        e.life += 1
        if (e.life > e.max) { embers.splice(i, 1); continue }
        e.x += e.vx
        e.y += e.vy
        e.vy -= 0.025
        e.vx *= 0.97
        const k = 1 - e.life / e.max
        c.fillStyle = `rgba(${pal.glow}, ${0.8 * k})`
        c.beginPath()
        c.arc(e.x, e.y, e.size * k + 0.3, 0, Math.PI * 2)
        c.fill()
      }
      c.restore()
    }
    gsap.ticker.add(tick)

    return () => {
      gsap.ticker.remove(tick)
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerdown', onDown)
      window.removeEventListener('resize', resize)
      root.removeEventListener('pointerleave', onLeave)
      root.classList.remove('dragon-cursor')
    }
  }, [enabled])
  return enabled ? createPortal(<canvas className="dragon-canvas" ref={ref} aria-hidden="true" />, document.body) : null
}
