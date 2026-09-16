import { useState } from 'react'
import { CheckCircle2, MailOpen, Send } from 'lucide-react'
import { newsletters } from '../data/editions.js'
import { stories } from '../data/stories.js'
import Reveal from './Reveal.jsx'
import NewsletterPersonalizer from './NewsletterPersonalizer.jsx'

const ACCENT = '#00F0FF'

function SubscribeForm({ compact = false }) {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState('')

  const submit = (e) => {
    e.preventDefault()
    const value = email.trim()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      setStatus('error')
      setError('Enter a valid email address to join the list.')
      return
    }
    setStatus('loading')
    setError('')
    window.setTimeout(() => setStatus('success'), 800)
  }

  if (status === 'success') {
    return (
      <div
        role="status"
        className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.04] p-4"
      >
        <CheckCircle2 className="h-5 w-5 shrink-0" style={{ color: ACCENT }} />
        <div>
          <p className="text-sm font-medium text-white">You are on the list.</p>
          <p className="text-sm text-white/55">
            First Crosscheck lands tomorrow morning. No spam, unsubscribe anytime.
          </p>
        </div>
      </div>
    )
  }

  return (
    <form onSubmit={submit} noValidate className={compact ? '' : 'mt-8 max-w-xl'}>
      <div className="flex flex-col gap-2 rounded-2xl bg-white p-1.5 shadow-2xl sm:flex-row sm:items-center sm:rounded-full">
        <label htmlFor="newsletter-email" className="sr-only">
          Email address
        </label>
        <input
          id="newsletter-email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value)
            if (status === 'error') setStatus('idle')
          }}
          placeholder="you@example.com"
          aria-invalid={status === 'error'}
          aria-describedby={status === 'error' ? 'newsletter-error' : undefined}
          className="w-full flex-1 rounded-xl bg-transparent px-4 py-2.5 text-sm text-gray-900 outline-none placeholder-gray-400 sm:rounded-full"
        />
        <button
          type="submit"
          disabled={status === 'loading'}
          className="flex items-center justify-center gap-2 rounded-xl px-6 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-60 sm:rounded-full"
          style={{
            background: 'linear-gradient(to bottom, #2B2B2B, #101010)',
            border: `1px solid ${ACCENT}4D`,
            boxShadow: '0 0 24px rgba(0, 240, 255, 0.18)',
          }}
        >
          <Send className="h-4 w-4" />
          {status === 'loading' ? 'Joining…' : 'Subscribe'}
        </button>
      </div>
      {status === 'error' ? (
        <p id="newsletter-error" role="alert" className="mt-2 pl-2 text-sm text-red-300">
          {error}
        </p>
      ) : (
        <p className="mt-2 pl-2 text-xs text-white/40">
          One email per edition. Read a sample below before you decide.
        </p>
      )}
    </form>
  )
}

export default function NewslettersPage({ onOpenStory }) {
  const [subscribed, setSubscribed] = useState(() => new Set(['the-crosscheck']))

  const toggle = (id) => {
    setSubscribed((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const sampleStory = stories[0]

  return (
    <div className="page-enter">
      <section className="relative overflow-hidden px-6 pb-12 pt-14 md:px-12 md:pt-20">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-40 left-1/2 h-96 w-[42rem] -translate-x-1/2 rounded-full opacity-20 blur-3xl"
          style={{ background: 'radial-gradient(closest-side, rgba(0,240,255,0.55), transparent)' }}
        />
        <div className="perspective-stage relative max-w-3xl">
          <p className="stagger-item eyebrow-kanit text-[12px] text-white/50" style={{ '--i': 0 }}>
            Newsletters
          </p>
          <h1
            className="stagger-item mt-3 font-display text-5xl font-extrabold leading-[1.02] tracking-tight text-white md:text-6xl"
            style={{ '--i': 1 }}
          >
            <span className="display-3d display-3d-gradient">The feed, distilled. Disagreement kept in.</span>
          </h1>
          <p className="stagger-item mt-4 max-w-xl font-display text-lg font-medium leading-relaxed text-white/70 md:text-xl" style={{ '--i': 2 }}>
            Each edition starts from cross-checked stories, shows where sources agree, and
            names the claim to treat with care. Pick the rhythm that fits your mornings.
          </p>
          <div className="stagger-item" style={{ '--i': 3 }}>
            <SubscribeForm />
          </div>
        </div>
      </section>

      <section className="px-6 pb-4 pt-6 md:px-12">
        <NewsletterPersonalizer />
      </section>

      <section className="px-6 pb-4 pt-6 md:px-12">
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          {newsletters.map((letter, i) => {
            const active = subscribed.has(letter.id)
            return (
              <article
                key={letter.id}
                style={{ '--i': i }}
                className="stagger-item lift flex flex-col rounded-2xl border border-white/10 bg-white/[0.04] p-6"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-white/50">
                    {letter.topic}
                  </span>
                  <span className="rounded-full border border-white/10 bg-black/40 px-3 py-1 text-xs text-white/60">
                    {letter.cadence}
                  </span>
                </div>
                <h2 className="card-title-3d mt-3 font-display text-2xl font-extrabold tracking-tight text-white">{letter.name}</h2>
                <p className="mt-2 text-sm leading-relaxed text-white/60">{letter.description}</p>
                <p className="mt-4 rounded-xl border border-white/10 bg-black/40 p-3 text-xs leading-relaxed text-white/50">
                  <span className="mb-1 flex items-center gap-1.5 font-medium text-white/70">
                    <MailOpen className="h-3.5 w-3.5" style={{ color: ACCENT }} />
                    In the latest issue
                  </span>
                  {letter.sample}
                </p>
                <button
                  type="button"
                  onClick={() => toggle(letter.id)}
                  aria-pressed={active}
                  className={`mt-5 rounded-full px-5 py-2.5 text-sm font-medium transition-colors ${
                    active
                      ? 'bg-white text-black hover:bg-white/85'
                      : 'border text-white hover:bg-white/10'
                  }`}
                  style={active ? undefined : { borderColor: `${ACCENT}4D` }}
                >
                  {active ? 'Subscribed' : `Subscribe to ${letter.name}`}
                </button>
              </article>
            )
          })}
        </div>
      </section>

      <Reveal className="px-6 py-12 md:px-12">
        <div className="grid grid-cols-1 gap-6 overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03] lg:grid-cols-2">
          <div className="p-8 md:p-10">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: ACCENT }}>
              Sample story
            </p>
            <h2 className="card-title-3d mt-3 font-display text-3xl font-extrabold tracking-tight text-white md:text-4xl">
              {sampleStory.title}
            </h2>
            <p className="mt-3 leading-relaxed text-white/60">{sampleStory.summary}</p>
            <div className="mt-5 flex items-center gap-3 text-sm text-white/50">
              <span className="rounded-full bg-white/10 px-3 py-1 font-semibold text-white">
                {sampleStory.consensus}% consensus
              </span>
              <span>{sampleStory.sources.length} sources cross-checked</span>
            </div>
            <button
              type="button"
              onClick={() => onOpenStory(sampleStory.id)}
              className="mt-7 rounded-full bg-white px-6 py-2.5 text-sm font-medium text-black transition-colors hover:bg-white/85"
            >
              Read this cross-check
            </button>
          </div>
          <div className="border-t border-white/10 bg-black/50 p-8 md:p-10 lg:border-l lg:border-t-0">
            <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-white/50">
              What subscribers see first
            </h3>
            <ul className="mt-4 space-y-3">
              {sampleStory.sources.slice(0, 3).map((source) => (
                <li key={source.outlet} className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                  <p className="text-sm font-medium text-white">{source.outlet}</p>
                  <p className="mt-1 text-sm text-white/55">{source.note}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Reveal>
    </div>
  )
}
