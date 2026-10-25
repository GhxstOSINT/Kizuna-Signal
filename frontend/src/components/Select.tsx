import { Check } from 'lucide-react'
import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import { useI18n } from '../i18n'

export type SelectOption = string | { value: string; label: string }

const normalise = (option: SelectOption) => typeof option === 'string' ? { value: option, label: option } : option

// The OS draws native <select> menus, so they look different on macOS and Windows and ignore the theme.
// Option labels are English source strings run through t(). This is a themed listbox with the same keyboard behaviour (arrows, Home/End, Enter/Space, Esc, type-ahead).
export function Select({ value, onChange, options, ariaLabel }: {
  value: string
  onChange: (value: string) => void
  options: SelectOption[]
  ariaLabel: string
}) {
  const { t } = useI18n()
  const items = options.map(normalise).map((item) => ({ ...item, label: t(item.label) }))
  const selected = Math.max(0, items.findIndex((item) => item.value === value))
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(selected)
  const [openUp, setOpenUp] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const listId = useId()

  useEffect(() => {
    if (!open) return
    const close = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false) }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [open])

  useEffect(() => {
    if (open) root.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: 'nearest' })
  }, [open, active])

  const openMenu = () => {
    const rect = trigger.current?.getBoundingClientRect()
    if (rect) {
      const below = window.innerHeight - rect.bottom
      setOpenUp(below < 300 && rect.top > below)
    }
    setActive(selected)
    setOpen(true)
  }
  const choose = (index: number) => {
    onChange(items[index].value)
    setOpen(false)
    trigger.current?.focus()
  }
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    const last = items.length - 1
    switch (event.key) {
      case 'ArrowDown': case 'ArrowUp': {
        event.preventDefault()
        if (!open) { openMenu(); return }
        setActive((index) => Math.min(last, Math.max(0, index + (event.key === 'ArrowDown' ? 1 : -1))))
        return
      }
      case 'Home': if (open) { event.preventDefault(); setActive(0) } return
      case 'End': if (open) { event.preventDefault(); setActive(last) } return
      case 'Enter': case ' ':
        event.preventDefault()
        if (open) choose(active); else openMenu()
        return
      case 'Escape': if (open) { event.preventDefault(); event.stopPropagation(); setOpen(false) } return
      case 'Tab': setOpen(false); return
    }
    if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      const letter = event.key.toLowerCase()
      const start = open ? active + 1 : selected + 1
      const hit = [...items.slice(start), ...items.slice(0, start)].find((item) => item.label.toLowerCase().startsWith(letter))
      if (hit) { if (!open) openMenu(); setActive(items.indexOf(hit)) }
    }
  }

  return <div className="select" ref={root}>
    <button
      ref={trigger}
      type="button"
      className="select-trigger"
      role="combobox"
      aria-label={t(ariaLabel)}
      aria-haspopup="listbox"
      aria-expanded={open}
      aria-controls={listId}
      aria-activedescendant={open ? `${listId}-${active}` : undefined}
      onClick={() => (open ? setOpen(false) : openMenu())}
      onKeyDown={onKeyDown}
      onBlur={() => setOpen(false)}
    >
      <span>{items[selected]?.label}</span>
    </button>
    {open && <ul
      id={listId}
      role="listbox"
      aria-label={t(ariaLabel)}
      className={`select-menu${openUp ? ' up' : ''}`}
      onMouseDown={(event) => event.preventDefault()}
      // Inside a <label>, a click would otherwise be forwarded to the trigger and reopen the menu.
      onClick={(event) => event.preventDefault()}
    >
      {items.map((item, index) => <li
        key={item.value}
        id={`${listId}-${index}`}
        data-index={index}
        role="option"
        aria-selected={index === selected}
        className={`select-option${index === active ? ' active' : ''}`}
        onMouseEnter={() => setActive(index)}
        onClick={() => choose(index)}
      ><span>{item.label}</span>{index === selected && <Check size={15} strokeWidth={2.2} aria-hidden="true" />}</li>)}
    </ul>}
  </div>
}
