import { useState } from 'react'
import { AtSign, CheckCircle2 } from 'lucide-react'

const TRENDING = ['morning-brief', 'climate-desk', 'good-news-only', 'harbor-city']

export default function DomainReserve() {
  const [handle, setHandle] = useState('')
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState('')

  const submit = (e) => {
    e.preventDefault()
    const value = handle.trim().toLowerCase()
    if (!/^[a-z0-9-]{3,20}$/.test(value)) {
      setStatus('error')
      setError('Use 3–20 characters: letters, numbers, hyphens.')
      return
    }
    setStatus('success')
    setError('')
  }

  return (
    <div id="reserve" className="t-card overflow-hidden rounded-2xl border">
      <div className="grid grid-cols-1 lg:grid-cols-2">
        <div className="p-8 md:p-10">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em]">weaware.news • early handles</p>
          <h2 className="mt-3 font-display text-3xl font-extrabold tracking-tight md:text-4xl">Reserve your name on weaware.news</h2>
          <p className="t-muted mt-3 text-sm leading-relaxed">
            A public page for your briefings, lists and shared cross-checks. Frontend mock — no backend, names are
            held locally in this preview.
          </p>

          {status === 'success' ? (
            <div role="status" className="t-card t-border mt-6 flex items-center gap-3 rounded-2xl border p-4">
              <CheckCircle2 className="h-5 w-5 shrink-0" />
              <div>
                <p className="text-sm font-medium">{handle.trim().toLowerCase()}.weaware.news is yours (mock).</p>
                <p className="t-muted text-sm">We will email you when handles go live.</p>
              </div>
            </div>
          ) : (
            <form onSubmit={submit} noValidate className="mt-6">
              <div className="t-card t-border flex flex-col gap-2 rounded-2xl border p-1.5 sm:flex-row sm:items-center sm:rounded-full">
                <div className="flex flex-1 items-center gap-1 px-3">
                  <AtSign className="t-faint h-4 w-4 shrink-0" />
                  <label htmlFor="reserve-handle" className="sr-only">Handle</label>
                  <input
                    id="reserve-handle"
                    value={handle}
                    onChange={(e) => {
                      setHandle(e.target.value)
                      if (status === 'error') setStatus('idle')
                    }}
                    placeholder="your-name"
                    autoComplete="off"
                    aria-invalid={status === 'error'}
                    className="t-field w-full bg-transparent py-2 text-sm outline-none"
                  />
                  <span className="t-faint hidden shrink-0 text-sm sm:block">.weaware.news</span>
                </div>
                <button type="submit" className="t-btn-primary rounded-xl px-6 py-2.5 text-sm font-medium sm:rounded-full">
                  Reserve
                </button>
              </div>
              {status === 'error' ? (
                <p role="alert" className="mt-2 pl-2 text-sm">{error}</p>
              ) : (
                <p className="t-faint mt-2 pl-2 font-mono text-xs">{handle.trim() ? `${handle.trim().toLowerCase()}.weaware.news` : 'your-name.weaware.news'} — live preview</p>
              )}
            </form>
          )}
        </div>

        <div className="t-border t-card border-t p-8 md:p-10 lg:border-l lg:border-t-0">
          <h3 className="t-muted text-sm font-semibold uppercase tracking-[0.14em]">Trending handles</h3>
          <ul className="mt-4 space-y-2.5">
            {TRENDING.map((name) => (
              <li key={name} className="t-card t-border flex items-center justify-between gap-3 rounded-xl border px-4 py-3">
                <span className="font-mono text-sm">{name}.weaware.news</span>
                <button type="button" onClick={() => setHandle(name)} className="t-btn-outline shrink-0 rounded-full px-3.5 py-1.5 text-xs">
                  Try it
                </button>
              </li>
            ))}
          </ul>
          <p className="t-faint mt-4 text-[11px] leading-relaxed">Mock only. Real availability checks + auth arrive with backend.</p>
        </div>
      </div>
    </div>
  )
}
