import { useEffect, useState } from 'react'
import { sendEmailVerification } from '@firebase/auth'
import { CheckCircle2, MailOpen, Scissors } from 'lucide-react'
import { newsletters } from '../data/editions.js'
import { useAuth } from '../auth/AuthContext.jsx'
import { API_BASE } from '../lib/api.js'
import Reveal from './Reveal.jsx'
import NewsletterPersonalizer from './NewsletterPersonalizer.jsx'
import NewsletterMasthead from './NewsletterMasthead.jsx'
import FrontPageGrid from './FrontPageGrid.jsx'

function SectionHeader({ index, title, blurb }) {
  return (
    <div className="flex items-center gap-4">
      <div className="t-border h-px flex-1 border-t" aria-hidden="true" />
      <div className="text-center">
        <p className="kicker">
          Section {index} {title}
        </p>
        {blurb ? <p className="t-muted mt-1 text-sm">{blurb}</p> : null}
      </div>
      <div className="t-border h-px flex-1 border-t" aria-hidden="true" />
    </div>
  )
}

export default function NewslettersPage({ onOpenStory, stories = [], topics = [] }) {
  const { user, configured, requestSignIn } = useAuth()
  const [selectedTopics, setSelectedTopics] = useState([])
  const [cadence, setCadence] = useState('weekly')
  const [deliveryReady, setDeliveryReady] = useState(false)
  const [consent, setConsent] = useState(false)
  const [isSubscribed, setIsSubscribed] = useState(false)
  const [preferencesLoading, setPreferencesLoading] = useState(false)
  const [preferencesSaving, setPreferencesSaving] = useState(false)
  const [emailVerified, setEmailVerified] = useState(Boolean(user?.emailVerified))
  const [preferencesMessage, setPreferencesMessage] = useState('')
  const [preferencesError, setPreferencesError] = useState('')

  useEffect(() => {
    let cancelled = false
    if (!user) {
      setEmailVerified(false)
      setSelectedTopics([])
      setCadence('weekly')
      setConsent(false)
      setIsSubscribed(false)
      setPreferencesMessage('')
      setPreferencesError('')
      return undefined
    }
    setEmailVerified(Boolean(user.emailVerified))
    setPreferencesLoading(true)
    user.getIdToken().then((token) => fetch(`${API_BASE}/api/v1/newsletters/preferences`, {
      headers: { Authorization: `Bearer ${token}` },
    })).then(async (response) => {
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload.detail || `Could not load newsletter settings (${response.status})`)
      if (cancelled) return
      setDeliveryReady(Boolean(payload.deliveryReady))
      setSelectedTopics(payload.topics || [])
      setCadence(payload.cadence || 'weekly')
      setConsent(Boolean(payload.subscribed))
      setIsSubscribed(Boolean(payload.subscribed))
      setPreferencesError('')
    }).catch((error) => {
      if (!cancelled) setPreferencesError(error.message || 'Newsletter settings are unavailable.')
    }).finally(() => {
      if (!cancelled) setPreferencesLoading(false)
    })
    return () => { cancelled = true }
  }, [user, API_BASE])

  const toggleTopic = (topic) => {
    setSelectedTopics((current) => current.includes(topic) ? current.filter((item) => item !== topic) : [...current, topic])
    setPreferencesMessage('')
  }

  const savePreferences = async () => {
    setPreferencesError('')
    setPreferencesMessage('')
    if (!user) return
    if (!emailVerified) {
      setPreferencesError('Verify your email address before subscribing.')
      return
    }
    if (!selectedTopics.length) {
      setPreferencesError('Choose at least one topic.')
      return
    }
    if (!consent) {
      setPreferencesError('Check the consent box to receive email briefings.')
      return
    }
    setPreferencesSaving(true)
    try {
      const token = await user.getIdToken()
      const response = await fetch(`${API_BASE}/api/v1/newsletters/preferences`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ topics: selectedTopics, cadence, consent: true }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload.detail || `Could not save settings (${response.status})`)
      setIsSubscribed(true)
      setConsent(true)
      setPreferencesMessage('Your newsletter preferences are saved.')
    } catch (error) {
      setPreferencesError(error.message || 'Could not save newsletter settings.')
    } finally {
      setPreferencesSaving(false)
    }
  }

  const sendTestEmail = async () => {
    setPreferencesSaving(true)
    setPreferencesError('')
    setPreferencesMessage('')
    try {
      const token = await user.getIdToken(true)
      const response = await fetch(`${API_BASE}/api/v1/newsletters/test`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}` },
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload.detail || 'Could not send the test email.')
      setPreferencesMessage(payload.message)
    } catch (error) {
      setPreferencesError(error.message)
    } finally {
      setPreferencesSaving(false)
    }
  }

  const verifyEmail = async () => {
    if (!user) return
    setPreferencesError('')
    setPreferencesMessage('')
    try {
      await sendEmailVerification(user)
      setPreferencesMessage('Verification email sent. After confirming it, use the button below to refresh your status.')
    } catch (error) {
      setPreferencesError(error.message || 'Could not send the verification email.')
    }
  }

  const refreshEmailVerification = async () => {
    if (!user) return
    await user.reload()
    await user.getIdToken(true)
    setEmailVerified(Boolean(user.emailVerified))
    setPreferencesMessage(user.emailVerified ? 'Email verified. You can now save your briefing.' : 'Your email is not verified yet. Open the verification email and try again.')
  }

  const unsubscribe = async () => {
    if (!user) return
    setPreferencesSaving(true)
    setPreferencesError('')
    setPreferencesMessage('')
    try {
      const token = await user.getIdToken()
      const response = await fetch(`${API_BASE}/api/v1/newsletters/preferences/unsubscribe`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}` },
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload.detail || `Could not unsubscribe (${response.status})`)
      setIsSubscribed(false)
      setConsent(false)
      setPreferencesMessage('You are unsubscribed. You can opt in again any time.')
    } catch (error) {
      setPreferencesError(error.message || 'Could not unsubscribe.')
    } finally {
      setPreferencesSaving(false)
    }
  }

  const ticker = stories.slice(0, 3).map((s) => ({ id: s.id, title: s.title, consensus: s.consensus }))
  const editionStories = stories
  const archive = stories.slice(6, 10)

  return (
    <div className="page-enter">
      <NewsletterMasthead ticker={ticker} />

      <section aria-label="The front page" className="t-border mt-6 border-y">
        <div className="mx-auto max-w-6xl px-6 pt-6 md:px-12">
          <Reveal>
            <SectionHeader index="A" title="The front page" blurb="One lead story, the source stances, and the claims worth a closer look." />
          </Reveal>
        </div>
        {editionStories.length ? (
          <FrontPageGrid stories={editionStories} onOpenStory={onOpenStory} />
        ) : (
          <div className="mx-auto max-w-6xl px-6 py-12 text-center md:px-12">
            <p className="kicker">The edition is coming together</p>
            <p className="t-muted mt-2 font-display text-xl">Fresh stories will appear here as soon as they’re ready.</p>
          </div>
        )}
      </section>
      {/* Section B: editions */}
      <section aria-label="Choose your section" className="px-6 py-10 md:px-12">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <SectionHeader index="B" title="Build your briefing" blurb="Choose the topics you care about and how often you want an email." />
          </Reveal>
          <div className="t-card t-border mt-8 border p-5 md:p-7">
            {!configured ? <p className="t-muted text-sm">Sign-in is not configured for this preview.</p> : !user ? (
              <div className="flex flex-col items-start justify-between gap-5 sm:flex-row sm:items-center">
                <div className="flex items-start gap-4">
                  <span className="t-border t-bg flex h-12 w-12 shrink-0 items-center justify-center rounded-full border" aria-hidden="true"><MailOpen className="h-5 w-5" /></span>
                  <div>
                    <p className="kicker">Your paper, your rules</p>
                    <h3 className="headline-serif mt-1 text-2xl">A briefing shaped around you.</h3>
                    <p className="t-muted mt-1 max-w-xl text-sm leading-relaxed">Choose your topics and delivery rhythm. We’ll send only the reporting you asked for.</p>
                  </div>
                </div>
                <button type="button" onClick={requestSignIn} className="t-btn-primary shrink-0 rounded-full px-5 py-2.5 text-sm font-medium">Sign in to personalize</button>
              </div>
            ) : (
              <div>
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="font-medium">Email delivery for {user.email}</p>
                    <p className="t-muted mt-1 text-sm">Only published articles matching your selected topics are included. Each subscriber receives a private email. To include other people, ask them to sign in and subscribe with their own address.</p>
                    {!emailVerified && <div className="mt-3 flex flex-wrap items-center gap-2 text-sm"><span className="t-muted">Verify this address before subscribing.</span><button type="button" onClick={verifyEmail} className="t-btn-outline rounded-full px-3 py-1.5 text-xs">Send verification email</button><button type="button" onClick={refreshEmailVerification} className="t-btn-outline rounded-full px-3 py-1.5 text-xs">I have verified</button></div>}
                  </div>
                  <label className="flex items-center gap-2 text-sm">
                    <span>Send me a briefing</span>
                    <select value={cadence} onChange={(event) => setCadence(event.target.value)} className="t-field rounded-lg border bg-transparent px-3 py-2">
                      <option value="daily">Daily</option>
                      <option value="weekly">Weekly</option>
                    </select>
                  </label>
                </div>
                {!preferencesLoading && !deliveryReady && <p role="status" className="mt-3 text-sm">Email delivery is awaiting configuration. You can save preferences, but emails will not be sent yet.</p>}
                <fieldset className="mt-5">
                  <legend className="text-sm font-medium">Choose topics</legend>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {topics.map((topic) => {
                      const selected = selectedTopics.includes(topic)
                      return <button key={topic} type="button" aria-pressed={selected} onClick={() => toggleTopic(topic)} className={`${selected ? 't-btn-primary' : 't-btn-outline'} rounded-full px-4 py-2 text-sm`}>{topic}</button>
                    })}
                    {!topics.length && <p className="t-muted text-sm">Topics will appear when published articles are available.</p>}
                  </div>
                </fieldset>
                <label className="t-muted mt-5 flex items-start gap-2 text-sm leading-relaxed">
                  <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} className="mt-1" />
                  <span>I agree to receive WeAware email briefings at the cadence shown. I can unsubscribe at any time.</span>
                </label>
                <div className="mt-5 flex flex-wrap items-center gap-3">
                  <button type="button" onClick={savePreferences} disabled={preferencesLoading || preferencesSaving || !topics.length} className="t-btn-primary rounded-full px-5 py-2.5 text-sm font-medium disabled:opacity-60">
                    {preferencesLoading ? 'Loading preferences…' : preferencesSaving ? 'Saving…' : isSubscribed ? 'Save preferences' : 'Subscribe to briefing'}
                  </button>
                  {isSubscribed && <button type="button" onClick={sendTestEmail} disabled={preferencesSaving || !deliveryReady} className="t-btn-outline rounded-full px-5 py-2.5 text-sm disabled:opacity-60">Send test email</button>}
                  {isSubscribed && <button type="button" onClick={unsubscribe} disabled={preferencesSaving} className="t-btn-outline rounded-full px-5 py-2.5 text-sm">Unsubscribe</button>}
                </div>
                {preferencesError && <p role="alert" className="mt-3 text-sm">{preferencesError}</p>}
                {preferencesMessage && <p role="status" className="mt-3 flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4" />{preferencesMessage}</p>}
              </div>
            )}
          </div>
          <div className="mt-8 grid grid-cols-1 gap-0 border t-border md:grid-cols-3">
            {newsletters.map((letter, i) => {
              const headlines = letter.sample.split(',').map((h) => h.trim())
              return (
                <article
                  key={letter.id}
                  style={{ '--i': i }}
                  className={`stagger-item flex flex-col p-6 md:p-7 ${i > 0 ? 't-border border-t md:border-l md:border-t-0' : ''}`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <p className="kicker">{letter.topic}</p>
                    <span aria-hidden="true" className="font-display text-4xl font-bold leading-none opacity-20">0{i + 1}</span>
                  </div>
                  <h2 className="headline-serif mt-1 text-3xl">{letter.name}</h2>
                  <p className="t-muted mt-1 text-xs font-semibold uppercase tracking-[0.14em]">{letter.cadence}</p>
                  <p className="t-muted font-body-serif mt-3 text-[15px] leading-relaxed">{letter.description}</p>
                  <div className="t-border mt-4 border-t pt-4">
                    <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.16em]">
                      <MailOpen className="h-3.5 w-3.5" />
                      In the latest issue
                    </p>
                    <ul className="mt-2 list-none space-y-1.5">
                      {headlines.map((h) => (
                        <li key={h} className="font-body-serif text-sm leading-snug">
                          <span className="t-faint mr-2">▪</span>
                          {h}
                        </li>
                      ))}
                    </ul>
                  </div>
                </article>
              )
            })}
          </div>
        </div>
      </section>

      {/* Coupon: personalizer */}
      <section aria-label="Personal briefing coupon" className="px-6 pb-4 md:px-12">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <div className="coupon-edge p-2">
              <div className="t-card t-border border p-6 md:p-8">
                <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em]">
                  <Scissors className="h-4 w-4" />
                  Clip and save: your Friday briefing
                </p>
                <p className="t-muted mt-2 max-w-2xl text-sm leading-relaxed">
                  Preview how selected topics shape a digest. Delivery settings above are saved securely to your signed-in account.
                </p>
                <div className="mt-6">
                  <NewsletterPersonalizer stories={editionStories} topics={topics} />
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Archive strip */}
      {archive.length > 0 && <section aria-label="Past issues" className="px-6 py-10 md:px-12">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <SectionHeader index="C" title="From the archive" blurb="Stories worth keeping on the record." />
          </Reveal>
          <div className={`t-border mt-8 grid grid-cols-1 gap-0 border sm:grid-cols-2 ${archive.length === 4 ? 'lg:grid-cols-4' : 'lg:grid-cols-3'}`}>
            {archive.map((s, i) => (
              <article
                key={s.id}
                className={`flex min-h-48 flex-col p-6 ${i > 0 ? 't-border border-t sm:border-l sm:border-t-0' : ''} ${i === 2 ? 'max-lg:border-t max-lg:sm:border-l-0' : ''} ${i === 3 ? 'max-lg:border-t max-lg:sm:border-l' : ''}`}
              >
                <p className="kicker">The back pages · {s.topic}</p>
                <h3 className="headline-serif mt-3 text-xl leading-snug">
                  <button type="button" onClick={() => onOpenStory(s.id)} className="text-left">
                    {s.title}
                  </button>
                </h3>
                <p className="t-faint mt-auto pt-4 text-xs">
                  {s.publishedAt} · {s.consensus}% consensus · {s.readMins} min read
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>}

      {/* Subscription folio */}
      <section aria-label="Subscribe" className="px-6 pb-14 md:px-12">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <div className="border p-1.5 t-border">
              <div className="t-card t-border border px-6 py-10 text-center md:px-12 md:py-12">
                <p className="kicker">Home delivery to your inbox</p>
                <h2 className="headline-serif mx-auto mt-3 max-w-2xl text-3xl md:text-4xl">
                  Get the morning paper without the pulp.
                </h2>
                <p className="t-muted font-body-serif mx-auto mt-3 max-w-xl text-[15px] leading-relaxed">
                  Sign in, choose topics, and set daily or weekly delivery. Every message includes an unsubscribe link.
                </p>
                <p className="t-faint mt-6 text-[11px] uppercase tracking-[0.16em]">
                  Set in Newsreader and Source Serif · Composed by WeAware Agents
                </p>
              </div>
            </div>
          </Reveal>
        </div>
      </section>
    </div>
  )
}
