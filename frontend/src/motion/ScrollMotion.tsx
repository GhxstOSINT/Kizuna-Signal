import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useLocation } from 'react-router-dom'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { SplitText } from 'gsap/SplitText'

gsap.registerPlugin(ScrollTrigger, SplitText)

// SplitText masks clip to the tight line-height, which cuts off descenders (g, y, p).
// Pad the mask downwards and pull the layout back so spacing stays the same.
function keepDescenders(masks: Element[]) {
  masks.forEach((mask) => { const { style } = mask as HTMLElement; style.paddingBottom = '0.2em'; style.marginBottom = '-0.2em' })
}

const REVEAL = [
  '.page > section',
  '.page > .stats-grid > *',
  '.analysis-list > *',
  '.region-map-figure, .region-detail',
  '.form-section',
  '.intake-aside',
  '.title-details dl > div',
  '.component-row',
  '.comparable-row',
  '.source-row',
  '.driver-columns > div',
  '.scenario-form',
].join(',')

export function prefersReducedMotion() {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

const NUMBER = /^(\d+(?:\.\d+)?)(%?)$/

const COUNTERS = '.stat strong, .score-main strong, .score-support dd'

function countUp(el: HTMLElement | null) {
  if (!el || el.dataset.gsa === '1') return
  const text = el.textContent?.trim() ?? ''
  if (el.dataset.gsc === text) return
  const match = NUMBER.exec(text)
  el.dataset.gsc = text
  if (!match || parseFloat(match[1]) === 0) return
  const target = parseFloat(match[1])
  const decimals = match[1].includes('.') ? match[1].split('.')[1].length : 0
  const state = { value: 0 }
  let last = ''
  el.dataset.gsa = '1'
  gsap.to(state, {
    value: target, duration: 1.6, ease: 'power3.out',
    onUpdate: () => { last = state.value.toFixed(decimals) + match[2]; el.textContent = last },
    onComplete: () => {
      el.dataset.gsa = ''
      if (el.textContent === last) el.textContent = text
      else el.dataset.gsc = ''
    },
  })
}

function countVisible() {
  document.querySelectorAll<HTMLElement>(COUNTERS).forEach((el) => {
    const r = el.getBoundingClientRect()
    if (r.top < window.innerHeight * 0.95 && r.bottom > 0 && getComputedStyle(el).visibility !== 'hidden') countUp(el)
  })
}

export function ScrollMotion() {
  const { pathname } = useLocation()
  useEffect(() => {
    if (prefersReducedMotion()) return
    const ctx = gsap.context(() => {
      const scan = () => {
        const fresh = Array.from(document.querySelectorAll<HTMLElement>(REVEAL)).filter((el) => !el.dataset.gs)
        if (!fresh.length) return
        fresh.forEach((el) => { el.dataset.gs = '1' })
        gsap.set(fresh, { opacity: 0, y: 38 })
        ScrollTrigger.batch(fresh, {
          start: 'top 92%',
          once: true,
          batchMax: 6,
          interval: 0.08,
          onEnter: (batch) => {
            batch.forEach((el) => {
              el.querySelectorAll<HTMLElement>(COUNTERS).forEach(countUp)
            })
            return gsap.to(batch, { opacity: 1, y: 0, duration: 0.9, ease: 'power3.out', stagger: 0.09, overwrite: true, clearProps: 'opacity,transform' })
          },
        })
        // fail-safe: never leave something above the fold hidden
        window.setTimeout(() => {
          fresh.forEach((el) => {
            if (el.isConnected && getComputedStyle(el).opacity === '0' && el.getBoundingClientRect().top < window.innerHeight) {
              gsap.to(el, { opacity: 1, y: 0, duration: 0.5, clearProps: 'opacity,transform' })
            }
          })
        }, 2500)
      }
      const hero = () => {
        const h2 = document.querySelector<HTMLElement>('.portfolio-hero h2:not([data-gsh])')
        if (!h2) return
        h2.dataset.gsh = '1'
        const split = SplitText.create(h2, { type: 'words', mask: 'words' })
        keepDescenders(split.masks)
        gsap.from(split.words, { yPercent: 105, opacity: 0, duration: 1.1, delay: curtainDelay() + 0.2, ease: 'expo.out', stagger: 0.09 })
      }
      const header = () => {
        const head = document.querySelector<HTMLElement>('.page-header:not([data-gsh])')
        if (!head) return
        head.dataset.gsh = '1'
        const title = head.querySelector<HTMLElement>('h1')
        if (title) {
          const split = SplitText.create(title, { type: 'lines,chars', mask: 'lines' })
          keepDescenders(split.masks)
          gsap.from(split.chars, { yPercent: 118, rotate: 7, opacity: 0, duration: 1.05, delay: curtainDelay(), ease: 'power4.out', stagger: 0.03 })
        }
        gsap.from('.jp-eyebrow', { x: -22, opacity: 0, duration: 0.9, delay: curtainDelay() + 0.1, ease: 'power3.out', clearProps: 'all' })
        gsap.from('.page-header p', { y: 14, opacity: 0, duration: 0.9, delay: curtainDelay() + 0.35, ease: 'power3.out', clearProps: 'all' })
        gsap.from('.kanji-mark', { scale: 0.7, rotate: -8, opacity: 0, delay: curtainDelay(), duration: 1.4, ease: 'expo.out', clearProps: 'opacity,scale,rotate' })
        gsap.to('.kanji-mark', { yPercent: -45, ease: 'none', scrollTrigger: { start: 0, end: 'max', scrub: 0.6 } })
        gsap.to('.page-header', { opacity: 0.35, ease: 'none', scrollTrigger: { trigger: '.page-header', start: 'bottom 30%', end: 'bottom -20%', scrub: true } })
      }
      gsap.fromTo('.scroll-progress', { scaleX: 0 }, { scaleX: 1, ease: 'none', scrollTrigger: { start: 0, end: 'max', scrub: 0.3 } })
      const curtain = document.querySelector('.page-curtain')
      const mountedAt = performance.now()
      const baseDelay = curtain ? 0.55 : 0
      const curtainDelay = () => Math.max(0, baseDelay - (performance.now() - mountedAt) / 1000)
      if (curtain) {
        gsap.timeline()
          .set(curtain, { display: 'grid', yPercent: 0 })
          .fromTo('.page-curtain span', { opacity: 0, scale: 0.6, rotate: -10 }, { opacity: 1, scale: 1, rotate: 0, duration: 0.3, ease: 'back.out(2)' })
          .to(curtain, { yPercent: -100, duration: 0.75, ease: 'power4.inOut' }, '+=0.08')
          .set(curtain, { display: 'none' })
      }
      requestAnimationFrame(() => { header(); hero(); scan() })
      let frame = 0
      const own = (node: Node) => {
        const el = node instanceof Element ? node : node.parentElement
        return Boolean(el?.closest('[data-gsa="1"]'))
      }
      const observer = new MutationObserver((records) => {
        // count-up text updates fire every frame; they must neither trigger nor starve a scan
        if (records.every((m) => own(m.target))) return
        countVisible()
        if (frame) return
        frame = requestAnimationFrame(() => {
          frame = 0
          ctx.add(() => { header(); hero(); scan() })
          ScrollTrigger.refresh()
        })
      })
      const root = document.querySelector('.workspace')
      if (root) observer.observe(root, { childList: true, subtree: true, characterData: true })
      return () => { observer.disconnect(); cancelAnimationFrame(frame) }
    })
    return () => ctx.revert()
  }, [pathname])
  return createPortal(<>
    <div className="scroll-progress" aria-hidden="true" />
    <div className="page-curtain" aria-hidden="true"><span lang="ja">絆</span></div>
  </>, document.body)
}
