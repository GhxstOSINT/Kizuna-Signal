import { Activity, BarChart3, BookOpen, FlaskConical, Github, LayoutGrid, Plus, ScrollText, Settings } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { applyLang, useI18n } from '../i18n'
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
  const { lang, t, setLang } = useI18n()
  const dark = theme === 'dark'
  const dragon = useDragonCursorSetting()
  const [settingsOpen, setSettingsOpen] = useState(false)
  useEffect(() => { applyLang(lang) }, [lang])
  return <div className="app-shell">
    <aside className="sidebar">
      <NavLink to="/" className="brand" aria-label={t('Kizuna Signal home')}>
        <span className="brand-mark" aria-hidden="true"><span /></span>
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
              <button type="button" lang="ja" aria-pressed={lang === 'ja'} onClick={() => setLang('ja')}>日本語</button>
              <button type="button" lang="en" aria-pressed={lang === 'en'} onClick={() => setLang('en')}>English</button>
            </span>
          </div>
          <button type="button" className="setting-row" role="switch" aria-checked={dark} onClick={toggle}>
            <span><strong>{t('Dark mode')}</strong><small>{t('Orange accents on a dark canvas')}</small></span>
            <span className="setting-track" aria-hidden="true" />
          </button>
          <button type="button" className="setting-row" role="switch" aria-checked={dragon.enabled} onClick={() => dragon.setEnabled(!dragon.enabled)}>
            <span><strong>{t('Dragon cursor')}</strong><small>{t('An ember-trailing serpent that follows your mouse')}</small></span>
            <span className="setting-track" aria-hidden="true" />
          </button>
        </div>}
        <p>{t('Pre-release intelligence for Japanese media entering India.')}</p>
        <div className="workspace-profile">
          <span className="workspace-profile-logo"><Github size={19} strokeWidth={1.8} /></span>
          <span><strong>@GhxstOSINT</strong><small>{t('Project team')}</small></span>
        </div>
      </div>
    </aside>
    <main className="workspace">{children}</main>
  </div>
}

export function SignalRail({ connected, label = 'Evidence system ready' }: { connected: boolean; label?: string }) {
  const { t } = useI18n()
  return <div className={`signal-rail ${connected ? 'is-live' : ''}`} role="status">
    <div className="spectral-line" aria-hidden="true" />
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
