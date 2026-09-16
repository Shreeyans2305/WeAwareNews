import { useState } from 'react'
import { AtSign, CheckCircle2 } from 'lucide-react'

const ACCENT = '#00F0FF'

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
    <div id="reserve" className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03]">
      <div className="grid grid-cols-1 lg:grid-cols-2">
        <div className="p-8 md:p-10">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: ACCENT }}>
            weaware.news • early handles
          </p>
          <h2 className="mt-3 font-display text-3xl font-extrabold tracking-tight text-white md:text-4xl">
            Reserve your name on weaware.news
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-white/60">
            A public page for your briefings, lists and shared cross-checks. Frontend mock — no
            backend, names are held locally in this preview.
          </p>

          {status === 'success' ? (
            <div role="status" className="mt-6 flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.04] p-4">
              <CheckCircle2 className="h-5 w-5 shrink-0" style={{ color: ACCENT }} />
              <div>
                <p className="text-sm font-medium text-white">{handle.trim().toLowerCase()}.weaware.news is yours (mock).</p>
                <p className="text-sm text-white/55">We will email you when handles go live.</p>
              </div>
            </div>
          ) : (
            <form onSubmit={submit} noValidate className="mt-6">
              <div className="flex flex-col gap-2 rounded-2xl bg-white p-1.5 shadow-2xl sm:flex-row sm:items-center sm:rounded-full">
                <div className="flex flex-1 items-center gap-1 px-3">
                  <AtSign className="h-4 w-4 shrink-0 text-gray-400" />
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
                    className="w-full bg-transparent py-2 text-sm text-gray-900 outline-none placeholder-gray-400"
                  />
                  <span className="hidden shrink-0 text-sm text-gray-400 sm:block">.weaware.news</span>
                </div>
                <button
                  type="submit"
                  className="rounded-xl px-6 py-2.5 text-sm font-medium text-white hover:opacity-90 sm:rounded-full"
                  style={{ background: 'linear-gradient(to bottom, #2B2B2B, #101010)', border: `1px solid ${ACCENT}4D` }}
                >
                  Reserve
                </button>
              </div>
              {status === 'error' ? (
                <p role="alert" className="mt-2 pl-2 text-sm text-red-300">{error}</p>
              ) : (
                <p className="mt-2 pl-2 font-mono text-xs text-white/40">
                  {handle.trim() ? `${handle.trim().toLowerCase()}.weaware.news` : 'your-name.weaware.news'} — live preview
                </p>
              )}
            </form>
          )}
        </div>

        <div className="border-t border-white/10 bg-black/50 p-8 md:p-10 lg:border-l lg:border-t-0">
          <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-white/50">Trending handles</h3>
          <ul className="mt-4 space-y-2.5">
            {TRENDING.map((name) => (
              <li key={name} className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3">
                <span className="font-mono text-sm text-white/80">{name}.weaware.news</span>
                <button
                  type="button"
                  onClick={() => setHandle(name)}
                  className="shrink-0 rounded-full border border-white/15 px-3.5 py-1.5 text-xs text-white/70 hover:bg-white/10 hover:text-white"
                >
                  Try it
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-[11px] leading-relaxed text-white/35">
            Mock only. Real availability checks + auth arrive with backend.
          </p>
        </div>
      </div>
    </div>
  )
}
