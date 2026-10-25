import { Activity, BarChart3, BookOpen, FlaskConical, LayoutGrid, LogOut, Plus, ScrollText, Settings } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../auth'
import { applyLang, useI18n } from '../i18n'
import { japaneseFor } from '../motion/jp'
import { FoxMark } from './FoxMark'
import { useDragonCursorSetting } from '../settings'
import { useTheme } from '../theme'

const nav = [
  { to: '/', label: 'Portfolio', icon: LayoutGrid },
  { to: '/new', label: 'New analysis', icon: Plus },
  { to: '/methodology', label: 'Methodology', icon: BookOpen },
]

export function AppShell({ children }: { children: ReactNode; connected?: boolean }) {
  const { theme, toggle } = useTheme()
  const { lang, t, setLang } = useI18n()
  const dark = theme === 'dark'
  const dragon = useDragonCursorSetting()
  const { user, signOut } = useAuth()
  const [settingsOpen, setSettingsOpen] = useState(false)
  const closeTimer = useRef<number>()
  useEffect(() => () => window.clearTimeout(closeTimer.current), [])
  // Apply a setting, then fold the panel back to the Settings button after the switch has visibly moved.
  const change = (apply: () => void) => {
    apply()
    window.clearTimeout(closeTimer.current)
    closeTimer.current = window.setTimeout(() => setSettingsOpen(false), 280)
  }
  useEffect(() => {
    applyLang(lang)
    document.title = lang === 'ja' ? '絆シグナル｜公開前インテリジェンス' : 'Kizuna Signal'
    document.querySelector('meta[name="description"]')?.setAttribute('content', t('Pre-release intelligence for Japanese media entering India.'))
  }, [lang, t])
  return <div className="app-shell">
    <aside className="sidebar">
      <NavLink to="/" className="brand" aria-label={t('Kizuna Signal home')}>
        <FoxMark className="brand-fox" size={30} />
        <span>Kizuna Signal</span>
        <span className="brand-kanji" lang="ja" aria-hidden="true">絆</span>
      </NavLink>
      <nav aria-label={t('Primary navigation')}>
        {nav.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} end={to === '/'} aria-label={t(label)} title={t(label)} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <Icon size={17} strokeWidth={1.7} /> <span>{t(label)}</span>
        </NavLink>)}
      </nav>
      <div className="sidebar-context">
        <button type="button" className="settings-button" aria-expanded={settingsOpen} aria-controls="settings-panel" onClick={() => setSettingsOpen((open) => !open)}>
          <Settings size={17} strokeWidth={1.7} />
          <span>{t('Settings')}</span>
        </button>
        {settingsOpen && <div className="settings-panel" id="settings-panel">
          <div className="setting-row static">
            <span><strong>{t('Language')}</strong><small>{t('Language of the interface')}</small></span>
            <span className="lang-switch" role="group" aria-label={t('Language')}>
              <button type="button" lang="ja" aria-pressed={lang === 'ja'} onClick={() => change(() => setLang('ja'))}>日本語</button>
              <button type="button" lang="en" aria-pressed={lang === 'en'} onClick={() => change(() => setLang('en'))}>English</button>
            </span>
          </div>
          <button type="button" className="setting-row" role="switch" aria-checked={dark} onClick={() => change(toggle)}>
            <span><strong>{t('Dark mode')}</strong><small>{t('Orange accents on a dark canvas')}</small></span>
            <span className="setting-track" aria-hidden="true" />
          </button>
          <button type="button" className="setting-row" role="switch" aria-checked={dragon.enabled} onClick={() => change(() => dragon.setEnabled(!dragon.enabled))}>
            <span><strong>{t('Dragon cursor')}</strong><small>{t('An ember-trailing serpent that follows your mouse')}</small></span>
            <span className="setting-track" aria-hidden="true" />
          </button>
        </div>}
        <p>{t('Pre-release intelligence for Japanese media entering India.')}</p>
        {user && <div className="workspace-profile">
          <span className="workspace-profile-logo">{user.avatar_url ? <img src={user.avatar_url} alt="" referrerPolicy="no-referrer" /> : user.name.slice(0, 1).toUpperCase()}</span>
          <span><strong>{user.name}</strong><small>{user.email || t('Your portfolio')}</small></span>
          <button type="button" className="sign-out" onClick={() => void signOut()} aria-label={t('Sign out')} title={t('Sign out')}><LogOut size={16} strokeWidth={1.8} /></button>
        </div>}
      </div>
    </aside>
    <main className="workspace">{children}</main>
  </div>
}

export function SignalRail({ connected, label = 'Evidence system ready' }: { connected: boolean; label?: string }) {
  const { t } = useI18n()
  return <div className={`signal-rail ${connected ? 'is-live' : ''}`} role="status">
    <span className="signal-dot" />
    <span>{connected ? t('LIVE API') : t('OFFLINE')}</span>
    <i />
    <span>{t(label)}</span>
    <i />
    <span>{t('EXPLAINABLE SCORING')}</span>
    <i />
    <span>{t('INDIA REGIONAL INTELLIGENCE')}</span>
  </div>
}

export function PageHeader({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  const { t } = useI18n()
  const jp = japaneseFor(title)
  return <header className="page-header">
    <span className="kanji-mark" lang="ja" aria-hidden="true">{jp.kanji}</span>
    <div><span className="jp-eyebrow" lang="ja">{jp.kanji} · {jp.kana}</span><h1>{t(title)}</h1><p>{t(description)}</p></div>
    {action && <div>{action}</div>}
  </header>
}

export const pageIcons = { Activity, BarChart3, FlaskConical, ScrollText }
