import { useEffect, useState } from 'react'
import { Github } from 'lucide-react'
import { API, api } from '../api'
import type { AuthProvider } from '../api/types'
import { FoxMark } from '../components/FoxMark'
import { useI18n } from '../i18n'

const failures: Record<string, string> = {
  not_configured: 'That sign-in method is not set up on this server yet.',
  denied: 'Sign-in was cancelled. Nothing was changed.',
  state: 'The sign-in link expired or came from another browser. Please try again.',
  provider: 'The provider could not complete the sign-in. Please try again.',
}

const GoogleMark = () => <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
  <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.6 17.7 9.5 24 9.5z" />
  <path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.2 5.5-4.7 7.2l7.6 5.9c4.4-4.1 6.9-10.1 6.9-17.6z" />
  <path fill="#FBBC05" d="M10.5 28.7a14.5 14.5 0 0 1 0-9.4l-7.9-6.1a24 24 0 0 0 0 21.6l7.9-6.1z" />
  <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.6-5.9c-2.1 1.4-4.9 2.3-8.3 2.3-6.3 0-11.6-4.1-13.5-9.8l-7.9 6.1C6.5 42.6 14.6 48 24 48z" />
</svg>

export function LoginPage() {
  const { t } = useI18n()
  const [providers, setProviders] = useState<AuthProvider[] | null>(null)
  const code = new URLSearchParams(window.location.search).get('error')
  useEffect(() => {
    api.authProviders().then((body) => setProviders(body.providers)).catch(() => setProviders([]))
  }, [])
  const enabled = (id: string) => providers?.find((provider) => provider.id === id)?.enabled ?? false
  const buttons = [
    { id: 'google', label: 'Continue with Google', icon: <GoogleMark /> },
    { id: 'github', label: 'Continue with GitHub', icon: <Github size={18} strokeWidth={1.8} /> },
  ]
  return <main className="login-page">
    <section className="login-card">
      <FoxMark className="brand-fox" size={46} />
      <h1>{t('Sign in to Kizuna Signal')}</h1>
      <p>{t('New here? Pick a provider and your own private portfolio is created the first time you sign in.')}</p>
      {code && <p className="login-error" role="alert">{t(failures[code] ?? failures.provider)}</p>}
      <div className="login-buttons">
        {buttons.map(({ id, label, icon }) => enabled(id)
          // A plain link: the browser leaves for the provider and comes back signed in.
          ? <a key={id} className="button ghost wide" href={`${API}/auth/${id}/login`}>{icon}{t(label)}</a>
          : <button key={id} type="button" className="button ghost wide" disabled title={providers ? t('Not configured on this server') : undefined}>{icon}{t(label)}</button>)}
      </div>
      {providers?.length === 0 && <p className="login-note">{t('The sign-in service could not be reached.')}</p>}
      {providers && providers.length > 0 && !providers.some((provider) => provider.enabled) && <p className="login-note">{t('No sign-in provider is configured on this server yet.')}</p>}
      <small>{t('We only read your name, email address and profile picture.')}</small>
    </section>
  </main>
}
