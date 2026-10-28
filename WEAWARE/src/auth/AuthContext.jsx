import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { onAuthStateChanged } from '@firebase/auth'
import { auth, authConfigured } from './firebase.js'
import { API_BASE } from '../lib/api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(!authConfigured)
  const [apiProfile, setApiProfile] = useState(null)
  const [apiStatus, setApiStatus] = useState('idle')
  const [signInRequest, setSignInRequest] = useState(0)

  const requestSignIn = useCallback(() => setSignInRequest((request) => request + 1), [])

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
    signInRequest,
    requestSignIn,
    getIdToken: () => user?.getIdToken() ?? Promise.resolve(null),
  }), [user, ready, apiProfile, apiStatus, signInRequest, requestSignIn])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
