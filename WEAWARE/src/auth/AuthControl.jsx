import { useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { signInEmail, signInGoogle, registerEmail, sendResetEmail, signOutUser } from './firebase.js'
import { useAuth } from './AuthContext.jsx'
import { useDialogFocus } from '../lib/useDialogFocus.js'

function authMessage(error) {
  const code = error?.code || ''
  if (code.includes('popup-closed-by-user')) return 'The sign-in window was closed before finishing.'
  if (code.includes('account-exists-with-different-credential')) return 'An account already exists with this email. Sign in with its original method first.'
  if (code.includes('email-already-in-use')) return 'An account already uses this email. Try signing in instead.'
  if (code.includes('invalid-credential') || code.includes('invalid-login-credentials')) return 'That email and password combination was not recognized.'
  if (code.includes('weak-password')) return 'Choose a stronger password with at least 8 characters.'
  if (code.includes('too-many-requests')) return 'Too many attempts. Wait a bit, then try again.'
  if (code.includes('unauthorized-domain')) return 'This site address is not authorized in Firebase Authentication yet.'
  return error?.message || 'Sign-in could not be completed. Please try again.'
}

function AuthDialog({ onClose }) {
  const { configured } = useAuth()
  const dialogRef = useRef(null)
  const [mode, setMode] = useState('sign-in')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useDialogFocus(dialogRef, onClose, true, 'input')

  const run = async (action) => {
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await action()
      onClose()
    } catch (reason) {
      setError(authMessage(reason))
    } finally {
      setBusy(false)
    }
  }

  const resetPassword = async () => {
    setBusy(true)
    setError('')
    setMessage('')
    try {
      if (!email.trim()) throw new Error('Enter your email address first.')
      await sendResetEmail(email)
      setMessage('Password reset email sent. Check your inbox.')
    } catch (reason) {
      setError(authMessage(reason))
    } finally {
      setBusy(false)
    }
  }

  return createPortal(
    <div className="fixed inset-0 z-[70] flex items-center justify-center overflow-y-auto bg-black/70 p-4 backdrop-blur-sm" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="auth-title" tabIndex={-1} className="t-card w-full max-w-md rounded-2xl border p-6 shadow-2xl sm:p-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="eyebrow-kanit t-muted text-xs">WEAWARE ACCOUNT</p>
            <h2 id="auth-title" className="mt-1 font-display text-3xl font-bold tracking-tight">
              {mode === 'reset' ? 'Reset password' : mode === 'create' ? 'Create your account' : 'Welcome back'}
            </h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close sign-in" className="t-btn-outline rounded-full px-3 py-1 text-sm">Close</button>
        </div>

        {!configured ? (
          <div role="status" className="t-border t-muted mt-5 rounded-xl border p-4 text-sm leading-relaxed">
            Sign-in is ready to connect, but Firebase is not configured for this app yet. Add the web app values from Firebase to <code>WEAWARE/.env.local</code>, then restart the development server.
          </div>
        ) : (
          <>
            {mode !== 'reset' && (
              <div className="mt-6">
                <button type="button" disabled={busy} onClick={() => run(signInGoogle)} className="t-btn-outline flex w-full items-center justify-center gap-2 rounded-xl px-3 py-2.5 text-sm font-medium disabled:opacity-50">
                  <span aria-hidden="true" className="font-bold">G</span> Google
                </button>
              </div>
            )}

            {mode !== 'reset' && <div className="my-5 flex items-center gap-3"><span className="t-border h-px flex-1 border-t" /><span className="t-faint text-xs">or use email</span><span className="t-border h-px flex-1 border-t" /></div>}

            <form onSubmit={(event) => {
              event.preventDefault()
              if (mode === 'reset') return resetPassword()
              return run(() => mode === 'create' ? registerEmail(email, password) : signInEmail(email, password))
            }} className="space-y-3">
              <label className="block text-sm font-medium" htmlFor="auth-email">Email address</label>
              <input id="auth-email" type="email" required autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} className="t-field w-full rounded-xl border bg-transparent px-4 py-3 text-sm outline-none" placeholder="you@example.com" />
              {mode !== 'reset' && <>
                <label className="block pt-1 text-sm font-medium" htmlFor="auth-password">Password</label>
                <input id="auth-password" type="password" required minLength={mode === 'create' ? 8 : undefined} autoComplete={mode === 'create' ? 'new-password' : 'current-password'} value={password} onChange={(event) => setPassword(event.target.value)} className="t-field w-full rounded-xl border bg-transparent px-4 py-3 text-sm outline-none" placeholder={mode === 'create' ? 'At least 8 characters' : 'Your password'} />
              </>}
              {error && <p role="alert" className="auth-error rounded-lg px-3 py-2 text-sm">{error}</p>}
              {message && <p role="status" className="auth-success rounded-lg px-3 py-2 text-sm">{message}</p>}
              <button type="submit" disabled={busy} className="t-btn-primary mt-2 w-full rounded-xl px-4 py-3 text-sm font-semibold disabled:opacity-50">
                {busy ? 'Please wait…' : mode === 'reset' ? 'Send reset link' : mode === 'create' ? 'Create account' : 'Sign in with email'}
              </button>
            </form>

            <div className="t-muted mt-5 flex flex-wrap justify-between gap-3 text-sm">
              {mode === 'sign-in' ? <>
                <button type="button" onClick={() => { setMode('reset'); setError(''); setMessage('') }} className="underline underline-offset-4">Forgot password?</button>
                <button type="button" onClick={() => { setMode('create'); setError(''); setMessage('') }} className="underline underline-offset-4">Create account</button>
              </> : <button type="button" onClick={() => { setMode('sign-in'); setError(''); setMessage('') }} className="underline underline-offset-4">Back to sign in</button>}
            </div>
            <p className="t-faint mt-6 text-center text-xs leading-relaxed">By continuing, you agree to use your account responsibly. We use Firebase Authentication to secure sign-in.</p>
          </>
        )}
      </section>
    </div>,
    document.body,
  )
}

export default function AuthControl() {
  const { user, ready, apiStatus } = useAuth()
  const [open, setOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  if (!ready) return <span className="t-faint px-2 text-xs">Checking account…</span>
  if (!user) return <>
    <button type="button" onClick={() => setOpen(true)} className="t-btn-outline rounded-full px-3 py-1.5 text-xs font-medium">Sign in</button>
    {open && <AuthDialog onClose={() => setOpen(false)} />}
  </>

  const displayName = user.displayName || user.email || 'Your account'
  return <div className="relative">
    <button type="button" onClick={() => setMenuOpen((value) => !value)} aria-expanded={menuOpen} aria-label={`Account: ${displayName}`} className="t-btn-outline flex max-w-36 items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium">
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/10 text-[10px]">{displayName[0]?.toUpperCase()}</span>
      <span className="truncate">{user.displayName || 'Account'}</span>
    </button>
    {menuOpen && <div className="glass-nav absolute right-0 top-full z-40 mt-2 w-64 rounded-xl border p-3 shadow-xl">
      <p className="truncate text-sm font-medium">{displayName}</p>
      {user.email && <p className="t-muted mt-1 truncate text-xs">{user.email}</p>}
      {apiStatus === 'unavailable' && <p className="t-faint mt-2 text-xs">API token verification is ready after the updated API is deployed.</p>}
      <button type="button" onClick={() => { setMenuOpen(false); signOutUser() }} className="t-btn-outline mt-3 w-full rounded-lg px-3 py-2 text-xs">Sign out</button>
    </div>}
  </div>
}
