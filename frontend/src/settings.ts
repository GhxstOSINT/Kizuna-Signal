import { useCallback, useSyncExternalStore } from 'react'

const KEY = 'kizuna-dragon-cursor'
const EVENT = 'kizuna-settings'
let memory = false

function read() {
  try { return localStorage.getItem(KEY) === 'on' } catch { return memory }
}

function subscribe(callback: () => void) {
  window.addEventListener(EVENT, callback)
  window.addEventListener('storage', callback)
  return () => {
    window.removeEventListener(EVENT, callback)
    window.removeEventListener('storage', callback)
  }
}

/** The dragon cursor is off until it is switched on in Settings. */
export function useDragonCursorSetting() {
  const enabled = useSyncExternalStore(subscribe, read, () => false)
  const setEnabled = useCallback((value: boolean) => {
    memory = value
    try { localStorage.setItem(KEY, value ? 'on' : 'off') } catch { /* storage unavailable */ }
    window.dispatchEvent(new Event(EVENT))
  }, [])
  return { enabled, setEnabled }
}
