import { getApp, getApps, initializeApp } from '@firebase/app'
import {
  GoogleAuthProvider,
  browserLocalPersistence,
  createUserWithEmailAndPassword,
  getAuth,
  sendPasswordResetEmail,
  setPersistence,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
} from '@firebase/auth'

const config = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
}

export const authConfigured = Object.values(config).every(Boolean)
export const auth = authConfigured
  ? getAuth(getApps().length ? getApp() : initializeApp(config))
  : null

async function persistSession() {
  if (!auth) throw new Error('Sign-in is not configured yet. Add the Firebase web app settings and restart the site.')
  await setPersistence(auth, browserLocalPersistence)
}

export async function signInEmail(email, password) {
  await persistSession()
  return signInWithEmailAndPassword(auth, email.trim(), password)
}

export async function registerEmail(email, password) {
  await persistSession()
  return createUserWithEmailAndPassword(auth, email.trim(), password)
}

export async function signInGoogle() {
  await persistSession()
  const provider = new GoogleAuthProvider()
  provider.setCustomParameters({ prompt: 'select_account' })
  return signInWithPopup(auth, provider)
}

export async function sendResetEmail(email) {
  await persistSession()
  return sendPasswordResetEmail(auth, email.trim())
}

export async function signOutUser() {
  if (auth) await signOut(auth)
}
