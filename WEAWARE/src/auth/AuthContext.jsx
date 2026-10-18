import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { onAuthStateChanged } from '@firebase/auth'
import { auth, authConfigured } from './firebase.js'

const AuthContext = createContext(null)
const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(!authConfigured)
  const [apiProfile, setApiProfile] = useState(null)
  const [apiStatus, setApiStatus] = useState('idle')

  useEffect(() => {
    if (!auth) return undefined
    return onAuthStateChanged(auth, (nextUser) => {
      setUser(nextUser)
      setReady(true)
      setApiProfile(null)
      setApiStatus(nextUser ? 'checking' : 'idle')
      if (!nextUser) return
      nextUser.getIdToken().then((token) => fetch(`${API_BASE}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      })).then(async (response) => {
        if (!response.ok) throw new Error(`API verification returned ${response.status}`)
        setApiProfile(await response.json())
        setApiStatus('verified')
      }).catch(() => setApiStatus('unavailable'))
    })
  }, [])

  const value = useMemo(() => ({
    user,
    ready,
    configured: authConfigured,
    apiProfile,
    apiStatus,
    getIdToken: () => user?.getIdToken() ?? Promise.resolve(null),
  }), [user, ready, apiProfile, apiStatus])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
