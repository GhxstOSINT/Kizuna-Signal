import { useCallback, useSyncExternalStore } from 'react'
import { ja } from './ja'
import { names } from './names'
import { titleNames } from './titles'
import { translateServer } from './server'

export type Lang = 'ja' | 'en'
export type Vars = Record<string, string | number>

const KEY = 'kizuna-lang'
const EVENT = 'kizuna-lang-change'
let memory: Lang = 'en'

/** The interface opens in English until the viewer switches it in Settings. */
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

const dictionary: Record<string, string> = { ...ja, ...names }
const lowerIndex = new Map<string, string>()
for (const [key, value] of Object.entries(dictionary)) {
  const lower = key.toLowerCase()
  if (!lowerIndex.has(lower)) lowerIndex.set(lower, value)
}

const lookup = (text: string): string | undefined => dictionary[text] ?? lowerIndex.get(text.toLowerCase())

/** Translate one word or a short list ("Hindi, Tamil" or "A · B") such as a state, language or genre. */
function word(value: string): string {
  const hit = lookup(value)
  if (hit) return hit
  if (/[,·]/.test(value)) return value.split(/\s*[,·]\s*/).map((part) => lookup(part) ?? part).join('、')
  return value
}

function japanese(text: string): string {
  return lookup(text) ?? translateServer(text, word, (sentence) => lookup(sentence) ?? translateServer(sentence, word, () => null)) ?? text
}

/** English strings are the keys; a missing Japanese entry falls back to the English text. */
export function translate(text: string, vars?: Vars, lang: Lang = currentLang()): string {
  const base = lang === 'ja' ? japanese(text) : text
  return vars ? base.replace(/\{(\w+)\}/g, (_, name: string) => String(vars[name] ?? `{${name}}`)) : base
}

const slug = (name: string) => name.toLowerCase().replace(/[^a-z0-9]/g, '')

/** The Japanese title of an anime the API names in English, or the name unchanged when it is not known. */
export function translateTitle(name: string, lang: Lang = currentLang()): string {
  return lang === 'ja' ? titleNames[slug(name)] ?? name : name
}

let reverse: Map<string, string> | null = null

/** The English key behind a Japanese word (a state, language or theme), so typed Japanese can be sent to the API. */
export function fromJapanese(token: string): string | undefined {
  if (!reverse) {
    reverse = new Map()
    for (const [key, value] of Object.entries(dictionary)) if (!key.includes('{') && !reverse.has(value)) reverse.set(value, key)
  }
  return reverse.get(token.trim())
}

/** Split a typed list on English or Japanese commas. */
export const splitList = (text: string) => text.split(/[,、，]\s*/).map((item) => item.trim()).filter(Boolean)

export function applyLang(lang: Lang) {
  document.documentElement.lang = lang
}

export function useI18n() {
  const lang = useSyncExternalStore(subscribe, currentLang, () => 'en' as Lang)
  const t = useCallback((text: string, vars?: Vars) => translate(text, vars, lang), [lang])
  const setLang = useCallback((next: Lang) => {
    memory = next
    try { localStorage.setItem(KEY, next) } catch { /* storage unavailable */ }
    applyLang(next)
    window.dispatchEvent(new Event(EVENT))
  }, [])
  const tt = useCallback((name: string) => translateTitle(name, lang), [lang])
  return { lang, t, tt, setLang }
}
