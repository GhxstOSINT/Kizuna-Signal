import { useEffect, useRef } from 'react'
import { gsap } from 'gsap'
import { prefersReducedMotion } from './ScrollMotion'

const MAGNETIC = '.button:not(:disabled), .row-action, .theme-toggle'
const TILT = '.stat, .region-lane, .seo-sheet, .score-field'

export function Interactions() {
  const spot = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (prefersReducedMotion() || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return
    const ctx = gsap.context(() => {
      const moveX = gsap.quickTo(spot.current, 'x', { duration: 0.7, ease: 'power3.out' })
      const moveY = gsap.quickTo(spot.current, 'y', { duration: 0.7, ease: 'power3.out' })
      let magnet: HTMLElement | null = null
      let tilt: HTMLElement | null = null
      const release = (el: HTMLElement | null, props: gsap.TweenVars) => {
        if (el) gsap.to(el, { ...props, duration: 0.9, ease: 'elastic.out(1, 0.45)', overwrite: 'auto' })
      }
      const ensureGlare = (el: HTMLElement) => {
        if (el.dataset.tilt) return
        el.dataset.tilt = '1'
        const glare = document.createElement('span')
        glare.className = 'glare'
        el.appendChild(glare)
      }
      const onMove = (event: PointerEvent) => {
        moveX(event.clientX)
        moveY(event.clientY)
        const target = event.target as HTMLElement
        const m = target.closest<HTMLElement>(MAGNETIC)
        if (m !== magnet) { release(magnet, { x: 0, y: 0 }); magnet = m }
        if (m) {
          const r = m.getBoundingClientRect()
          gsap.to(m, { x: (event.clientX - (r.left + r.width / 2)) * 0.28, y: (event.clientY - (r.top + r.height / 2)) * 0.4, duration: 0.35, ease: 'power3.out', overwrite: 'auto' })
        }
        const t = target.closest<HTMLElement>(TILT)
        if (t !== tilt) { release(tilt, { rotationX: 0, rotationY: 0, scale: 1 }); tilt = t }
        if (t) {
          ensureGlare(t)
          const r = t.getBoundingClientRect()
          const px = (event.clientX - r.left) / r.width
          const py = (event.clientY - r.top) / r.height
          t.style.setProperty('--gx', `${px * 100}%`)
          t.style.setProperty('--gy', `${py * 100}%`)
          gsap.to(t, { rotationY: (px - 0.5) * 9, rotationX: (0.5 - py) * 7, scale: 1.015, transformPerspective: 900, duration: 0.45, ease: 'power2.out', overwrite: 'auto' })
        }
      }
      const onLeave = () => {
        release(magnet, { x: 0, y: 0 }); magnet = null
        release(tilt, { rotationX: 0, rotationY: 0, scale: 1 }); tilt = null
        gsap.to(spot.current, { opacity: 0, duration: 0.4 })
      }
      const onEnter = () => gsap.to(spot.current, { opacity: 1, duration: 0.5 })
      document.addEventListener('pointermove', onMove, { passive: true })
      document.documentElement.addEventListener('pointerleave', onLeave)
      document.documentElement.addEventListener('pointerenter', onEnter)
      return () => {
        document.removeEventListener('pointermove', onMove)
        document.documentElement.removeEventListener('pointerleave', onLeave)
        document.documentElement.removeEventListener('pointerenter', onEnter)
      }
    })
    return () => ctx.revert()
  }, [])
  return <div className="spotlight" ref={spot} aria-hidden="true" />
}
