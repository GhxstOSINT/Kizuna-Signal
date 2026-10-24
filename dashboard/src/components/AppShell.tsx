import { Activity, BarChart3, BookOpen, FlaskConical, Github, LayoutGrid, Plus, ScrollText } from 'lucide-react'
import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

const nav = [
  { to: '/', label: 'Portfolio', icon: LayoutGrid },
  { to: '/new', label: 'New analysis', icon: Plus },
  { to: '/methodology', label: 'Methodology', icon: BookOpen },
]

export function AppShell({ children }: { children: ReactNode; connected?: boolean }) {
  return <div className="app-shell">
    <aside className="sidebar">
      <NavLink to="/" className="brand" aria-label="Kizuna Signal home">
        <span className="brand-mark" aria-hidden="true"><span /></span>
        <span>Kizuna Signal</span>
      </NavLink>
      <nav aria-label="Primary navigation">
        {nav.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} end={to === '/'} aria-label={label} title={label} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <Icon size={17} strokeWidth={1.7} /> <span>{label}</span>
        </NavLink>)}
      </nav>
      <div className="sidebar-context">
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
  return <header className="page-header">
    <div><h1>{title}</h1><p>{description}</p></div>
    {action && <div>{action}</div>}
  </header>
}

export const pageIcons = { Activity, BarChart3, FlaskConical, ScrollText }
