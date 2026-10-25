import { useLayoutEffect } from 'react'
import { useLocation } from 'react-router-dom'

/** Start every page at the top; the router keeps the previous page's scroll position by default.
 *  `html` has `scroll-behavior: smooth`, which a new page's layout shift cancels mid-animation,
 *  so jump instantly, before paint. */
export function ScrollToTop() {
  const { pathname } = useLocation()
  useLayoutEffect(() => { window.scrollTo({ top: 0, left: 0, behavior: 'instant' }) }, [pathname])
  return null
}
