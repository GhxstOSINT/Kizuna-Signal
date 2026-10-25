import { useEffect, useRef } from 'react'
import { gsap } from 'gsap'
import { prefersReducedMotion } from './ScrollMotion'

const PETALS = 16

export function Sakura() {
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (prefersReducedMotion() || !box.current) return
    const ctx = gsap.context(() => {
      gsap.utils.toArray<HTMLElement>('.sakura-petal').forEach((petal) => {
        const size = gsap.utils.random(9, 20)
        gsap.set(petal, { width: size, height: size * 0.8, x: gsap.utils.random(0, window.innerWidth), y: -40, rotation: gsap.utils.random(0, 360), opacity: gsap.utils.random(0.35, 0.8) })
        gsap.to(petal, { y: window.innerHeight + 60, duration: gsap.utils.random(14, 26), ease: 'none', repeat: -1, delay: -gsap.utils.random(0, 24) })
        gsap.to(petal, { x: `+=${gsap.utils.random(-90, 90)}`, duration: gsap.utils.random(3, 6), ease: 'sine.inOut', yoyo: true, repeat: -1 })
        gsap.to(petal, { rotation: `+=${gsap.utils.random(120, 300)}`, rotationX: gsap.utils.random(0, 70), duration: gsap.utils.random(5, 9), ease: 'sine.inOut', yoyo: true, repeat: -1 })
      })
    }, box)
    return () => ctx.revert()
  }, [])
  return <div className="sakura" ref={box} aria-hidden="true">{Array.from({ length: PETALS }, (_, i) => <span className="sakura-petal" key={i} />)}</div>
}
