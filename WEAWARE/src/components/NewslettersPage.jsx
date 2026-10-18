import { useState } from 'react'
import { CheckCircle2, MailOpen, Scissors, Send } from 'lucide-react'
import { newsletters } from '../data/editions.js'
import Reveal from './Reveal.jsx'
import NewsletterPersonalizer from './NewsletterPersonalizer.jsx'
import NewsletterMasthead from './NewsletterMasthead.jsx'
import FrontPageGrid from './FrontPageGrid.jsx'

function SubscribeForm({ id = 'newsletter-email', large = false }) {
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
      <div role="status" className="t-card t-border flex items-center gap-3 border p-4">
        <CheckCircle2 className="h-5 w-5 shrink-0" />
        <div>
          <p className="text-sm font-medium">You are on the list.</p>
          <p className="t-muted text-sm">First Crosscheck lands tomorrow morning. No spam, unsubscribe anytime.</p>
        </div>
      </div>
    )
  }

  return (
    <form onSubmit={submit} noValidate className={large ? 'mx-auto mt-6 max-w-xl' : 'mt-4'}>
      <div className="t-card t-border flex flex-col gap-2 border p-1.5 sm:flex-row sm:items-center">
        <label htmlFor={id} className="sr-only">
          Email address
        </label>
        <input
          id={id}
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value)
            if (status === 'error') setStatus('idle')
          }}
          placeholder="you@example.com"
          aria-invalid={status === 'error'}
          aria-describedby={status === 'error' ? `${id}-error` : undefined}
          className="t-field w-full flex-1 bg-transparent px-4 py-2.5 text-sm outline-none"
        />
        <button
          type="submit"
          disabled={status === 'loading'}
          className="t-btn-primary flex items-center justify-center gap-2 px-6 py-2.5 text-sm font-medium disabled:opacity-60"
        >
          <Send className="h-4 w-4" />
          {status === 'loading' ? 'Joining…' : 'Subscribe'}
        </button>
      </div>
      {status === 'error' ? (
        <p id={`${id}-error`} role="alert" className="mt-2 pl-2 text-sm">
          {error}
        </p>
      ) : (
        <p className="t-faint mt-2 pl-2 text-xs">One email per edition. Read a sample below before you decide.</p>
      )}
    </form>
  )
}

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
  const [subscribed, setSubscribed] = useState(() => new Set(['the-crosscheck']))

  const toggle = (id) => {
    setSubscribed((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const ticker = stories.slice(0, 3).map((s) => ({ id: s.id, title: s.title, consensus: s.consensus }))
  const archive = stories.slice(10, 14)

  return (
    <div className="page-enter">
      <NewsletterMasthead ticker={ticker} />

      <div className="t-border mx-6 mt-6 border md:mx-12">
        <div className="mx-auto max-w-6xl">
          <FrontPageGrid stories={stories} onOpenStory={onOpenStory} />
        </div>
      </div>

      {/* Section B: editions */}
      <section aria-label="Choose your section" className="px-6 py-10 md:px-12">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <SectionHeader index="B" title="Choose your section" blurb="Three editions. Pick the rhythm that fits your mornings." />
          </Reveal>
          <div className="mt-8 grid grid-cols-1 gap-0 border t-border md:grid-cols-3">
            {newsletters.map((letter, i) => {
              const active = subscribed.has(letter.id)
              const headlines = letter.sample.split(',').map((h) => h.trim())
              return (
                <article
                  key={letter.id}
                  style={{ '--i': i }}
                  className={`stagger-item flex flex-col p-6 md:p-7 ${i > 0 ? 't-border border-t md:border-l md:border-t-0' : ''}`}
                >
                  <p className="kicker">{letter.topic}</p>
                  <h2 className="headline-serif mt-2 text-3xl">{letter.name}</h2>
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
                  <button
                    type="button"
                    onClick={() => toggle(letter.id)}
                    aria-pressed={active}
                    className={
                      active
                        ? 't-btn-primary mt-6 px-5 py-2.5 text-sm font-medium'
                        : 't-btn-outline mt-6 px-5 py-2.5 text-sm font-medium'
                    }
                  >
                    {active ? 'Subscribed' : `Subscribe to ${letter.name}`}
                  </button>
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
                  Pick topics once. We mock the email you would get, with consensus kept in and outrage left
                  out. Saved locally, frontend only.
                </p>
                <div className="mt-6">
                  <NewsletterPersonalizer stories={stories} topics={topics} />
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Archive strip */}
      <section aria-label="Past issues" className="px-6 py-10 md:px-12">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <SectionHeader index="C" title="From the archive" blurb="Recent issues. Every claim traceable to its sources." />
          </Reveal>
          <div className="t-border mt-8 grid grid-cols-1 gap-0 border sm:grid-cols-2 lg:grid-cols-4">
            {archive.map((s, i) => (
              <article
                key={s.id}
                className={`p-6 ${i > 0 ? 't-border border-t sm:border-l sm:border-t-0' : ''} ${
                  i === 2 ? 'max-lg:border-t max-lg:sm:border-l-0' : ''
                } ${i === 3 ? 'max-lg:border-t max-lg:sm:border-l' : ''}`}
              >
                <p className="kicker">
                  Issue No. {13 - i} · {s.topic}
                </p>
                <h3 className="headline-serif mt-2 text-lg leading-snug">
                  <button type="button" onClick={() => onOpenStory(s.id)} className="text-left">
                    {s.title}
                  </button>
                </h3>
                <p className="t-faint mt-2 text-xs">
                  {s.publishedAt} · {s.consensus}% consensus · {s.readMins} min
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

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
                  One email per edition. Cross-checked stories, source stances, and one flagged claim to read
                  twice.
                </p>
                <SubscribeForm id="newsletter-email-folio" large />
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
