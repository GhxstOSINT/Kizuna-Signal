import { useEffect } from 'react'
import { gsap } from 'gsap'
import { prefersReducedMotion } from './ScrollMotion'

const JELLY = '.model-proof-grid article, .source-row, .title-details dl > div'
const clamp = (value: number, limit: number) => Math.max(-limit, Math.min(limit, value))

export function Interactions() {
  useEffect(() => {
    if (prefersReducedMotion() || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return
    const ctx = gsap.context(() => {
      let jelly: HTMLElement | null = null
      let lastKick = 0
      const settle = (el: HTMLElement | null) => {
        if (!el) return
        gsap.killTweensOf(el)
        gsap.to(el, { x: 0, y: 0, rotation: 0, scaleX: 1, scaleY: 1, skewX: 0, skewY: 0, duration: 1.4, ease: 'elastic.out(1.1, 0.2)' })
      }
      // Push the card with the pointer's velocity, then let a spring pull it back so it wobbles.
      const kick = (el: HTMLElement, vx: number, vy: number) => {
        const speed = Math.min(Math.hypot(vx, vy), 40)
        gsap.killTweensOf(el)
        gsap.timeline()
          .to(el, {
            x: clamp(vx * 0.7, 14), y: clamp(vy * 0.7, 14), rotation: clamp(vx * 0.1, 2.5),
            scaleX: 1 + speed * 0.0015 + Math.abs(vx) * 0.0012, scaleY: 1 + speed * 0.0015 + Math.abs(vy) * 0.0012,
            skewX: clamp(vx * 0.08, 2), duration: 0.12, ease: 'power2.out',
          })
          .to(el, { x: 0, y: 0, rotation: 0, scaleX: 1.012, scaleY: 1.012, skewX: 0, duration: 1.3, ease: 'elastic.out(1.15, 0.18)' })
      }
      const onMove = (event: PointerEvent) => {
        const target = event.target as HTMLElement
        const t = target.closest('.analysis-page') ? null : target.closest<HTMLElement>(JELLY)
        if (t !== jelly) {
          settle(jelly)
          jelly = t
          if (t) kick(t, event.movementX, event.movementY)
        } else if (t && (Math.abs(event.movementX) > 3 || Math.abs(event.movementY) > 3) && event.timeStamp - lastKick > 90) {
          lastKick = event.timeStamp
          kick(t, event.movementX, event.movementY)
        }
      }
      const onLeave = () => {
        settle(jelly)
        jelly = null
      }
      document.addEventListener('pointermove', onMove, { passive: true })
      document.documentElement.addEventListener('pointerleave', onLeave)
      return () => {
        document.removeEventListener('pointermove', onMove)
        document.documentElement.removeEventListener('pointerleave', onLeave)
      }
    })
    return () => ctx.revert()
  }, [])
  return null
}
