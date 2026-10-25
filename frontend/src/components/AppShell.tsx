import { Activity, BarChart3, BookOpen, FlaskConical, Github, LayoutGrid, Plus, ScrollText, Settings } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { japaneseFor } from '../motion/jp'
import { useDragonCursorSetting } from '../settings'
import { useTheme } from '../theme'

const nav = [
  { to: '/', label: 'Portfolio', icon: LayoutGrid },
  { to: '/new', label: 'New analysis', icon: Plus },
  { to: '/methodology', label: 'Methodology', icon: BookOpen },
]

export function AppShell({ children }: { children: ReactNode; connected?: boolean }) {
  const { theme, toggle } = useTheme()
  const dark = theme === 'dark'
  const dragon = useDragonCursorSetting()
  const [settingsOpen, setSettingsOpen] = useState(false)
  return <div className="app-shell">
    <aside className="sidebar">
      <NavLink to="/" className="brand" aria-label="Kizuna Signal home">
        <span className="brand-mark" aria-hidden="true"><span /></span>
        <span>Kizuna Signal</span>
        <span className="brand-kanji" lang="ja" aria-hidden="true">絆</span>
      </NavLink>
      <nav aria-label="Primary navigation">
        {nav.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} end={to === '/'} aria-label={label} title={label} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <Icon size={17} strokeWidth={1.7} /> <span>{label}</span>
        </NavLink>)}
      </nav>
      <div className="sidebar-context">
        <button type="button" className="settings-button" aria-expanded={settingsOpen} aria-controls="settings-panel" onClick={() => setSettingsOpen((open) => !open)}>
          <Settings size={17} strokeWidth={1.7} />
          <span>Settings</span>
        </button>
        {settingsOpen && <div className="settings-panel" id="settings-panel">
          <button type="button" className="setting-row" role="switch" aria-checked={dark} onClick={toggle}>
            <span><strong>Dark mode</strong><small>Orange accents on a dark canvas</small></span>
            <span className="setting-track" aria-hidden="true" />
          </button>
          <button type="button" className="setting-row" role="switch" aria-checked={dragon.enabled} onClick={() => dragon.setEnabled(!dragon.enabled)}>
            <span><strong>Dragon cursor</strong><small>An ember-trailing serpent that follows your mouse</small></span>
            <span className="setting-track" aria-hidden="true" />
          </button>
        </div>}
        <p>Pre-release intelligence for Japanese media entering India.</p>
        <div className="workspace-profile">
          <span className="workspace-profile-logo"><Github size={19} strokeWidth={1.8} /></span>
          <span><strong>@GhxstOSINT</strong><small>Project team</small></span>
        </div>
      </div>
    </aside>
    <main className="workspace">{children}</main>
  </div>
}

export function SignalRail({ connected, label = 'Evidence system ready' }: { connected: boolean; label?: string }) {
  return <div className={`signal-rail ${connected ? 'is-live' : ''}`} role="status">
    <div className="spectral-line" aria-hidden="true" />
    <span className="signal-dot" />
    <span>{connected ? 'LIVE API' : 'OFFLINE'}</span>
    <i />
    <span>{label}</span>
    <i />
    <span>EXPLAINABLE SCORING</span>
    <i />
    <span>INDIA REGIONAL INTELLIGENCE</span>
  </div>
}

export function PageHeader({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  const jp = japaneseFor(title)
  return <header className="page-header">
    <span className="kanji-mark" lang="ja" aria-hidden="true">{jp.kanji}</span>
    <div><span className="jp-eyebrow" lang="ja">{jp.kanji} · {jp.kana}</span><h1>{title}</h1><p>{description}</p></div>
    {action && <div>{action}</div>}
  </header>
}

export const pageIcons = { Activity, BarChart3, FlaskConical, ScrollText }
