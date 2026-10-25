import { useEffect, useRef, useState } from 'react'

const HEADROOM = 28
const CREEP_CEILING = 95

/**
 * The backend reports progress in a few big steps (10, 55, 100). This eases the displayed value
 * toward each reported step and, while waiting for the next one, creeps slowly forward without
 * ever passing `reported + HEADROOM` or CREEP_CEILING. It never goes backwards and only reaches
 * 100 once the backend does.
 */
export function useSmoothProgress(reported: number): number {
  const [shown, setShown] = useState(0)
  const target = useRef(reported)
  const value = useRef(0)
  target.current = reported

  useEffect(() => {
    let frame = 0
    let last = performance.now()
    const tick = (now: number) => {
      const dt = Math.min(now - last, 100)
      last = now
      const reportedNow = target.current
      let next = value.current
      if (next < reportedNow) {
        next += Math.max((reportedNow - next) * (1 - Math.exp(-dt / 320)), dt * 0.004)
        next = Math.min(next, reportedNow)
      } else if (reportedNow < 100) {
        const ceiling = Math.min(reportedNow + HEADROOM, CREEP_CEILING)
        next += Math.max(ceiling - next, 0) * dt * 0.00007
      }
      if (next !== value.current) {
        value.current = next
        setShown(next)
      }
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [])

  return shown
}
