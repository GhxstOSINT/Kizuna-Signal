import { useCallback, useSyncExternalStore } from 'react'
import { ja } from './ja'

export type Lang = 'ja' | 'en'
export type Vars = Record<string, string | number>

const KEY = 'kizuna-lang'
const EVENT = 'kizuna-lang-change'
let memory: Lang = 'ja'

/** The interface opens in Japanese until the viewer switches it in Settings. */
export function currentLang(): Lang {
  try {
    const saved = localStorage.getItem(KEY)
    if (saved === 'en' || saved === 'ja') return saved
  } catch { /* storage unavailable */ }
  return memory
}

function subscribe(callback: () => void) {
  window.addEventListener(EVENT, callback)
  window.addEventListener('storage', callback)
  return () => {
    window.removeEventListener(EVENT, callback)
    window.removeEventListener('storage', callback)
  }
}

/** English strings are the keys; a missing Japanese entry falls back to the English text. */
export function translate(text: string, vars?: Vars, lang: Lang = currentLang()): string {
  const base = lang === 'ja' ? ja[text] ?? text : text
  return vars ? base.replace(/\{(\w+)\}/g, (_, name: string) => String(vars[name] ?? `{${name}}`)) : base
}

export function applyLang(lang: Lang) {
  document.documentElement.lang = lang
}

export function useI18n() {
  const lang = useSyncExternalStore(subscribe, currentLang, () => 'ja' as Lang)
  const t = useCallback((text: string, vars?: Vars) => translate(text, vars, lang), [lang])
  const setLang = useCallback((next: Lang) => {
    memory = next
    try { localStorage.setItem(KEY, next) } catch { /* storage unavailable */ }
    applyLang(next)
    window.dispatchEvent(new Event(EVENT))
  }, [])
  return { lang, t, setLang }
}
