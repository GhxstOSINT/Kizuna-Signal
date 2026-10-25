import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, UNAUTHORIZED_EVENT } from './api'
import type { User } from './api/types'

type Auth = {
  /** undefined while the session is being checked, null when signed out. */
  user: User | null | undefined
  signOut: () => Promise<void>
}

const AuthContext = createContext<Auth>({ user: undefined, signOut: async () => {} })

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null | undefined>(undefined)
  useEffect(() => {
    let active = true
    api.me()
      .then((me) => { if (active) setUser(me) })
      .catch(() => { if (active) setUser(null) })
    // Any API call that comes back 401 means the session ended (expired, or signed out in another tab).
    const expired = () => setUser(null)
    window.addEventListener(UNAUTHORIZED_EVENT, expired)
    return () => { active = false; window.removeEventListener(UNAUTHORIZED_EVENT, expired) }
  }, [])
  const signOut = useCallback(async () => {
    await api.logout().catch(() => undefined)
    setUser(null)
  }, [])
  const value = useMemo(() => ({ user, signOut }), [user, signOut])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
