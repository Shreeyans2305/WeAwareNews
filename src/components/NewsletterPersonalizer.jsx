import { useState } from 'react'
import { CheckCircle2, MailOpen, Sparkles } from 'lucide-react'
import { TOPICS, stories } from '../data/stories.js'

const ACCENT = '#00F0FF'

export default function NewsletterPersonalizer() {
  const [selected, setSelected] = useState(() => new Set(['AI', 'Good News']))
  const [cadence, setCadence] = useState('weekly')
  const [length, setLength] = useState('7 min')

  const toggleTopic = (topic) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(topic)) next.delete(topic)
      else next.add(topic)
      return next
    })
  }

  const previewStories = stories
    .filter((s) => selected.size === 0 || selected.has(s.topic))
    .slice(0, 3)

  const [saved, setSaved] = useState(false)

  return (
    <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03]">
      <div className="grid grid-cols-1 lg:grid-cols-2">
        <div className="p-8 md:p-10">
          <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: ACCENT }}>
            <Sparkles className="h-3.5 w-3.5" />
            Weekly personalised • mock
          </p>
          <h2 className="mt-3 font-display text-3xl font-extrabold tracking-tight text-white">
            Your Friday briefing, tuned to you
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-white/60">
            Pick topics once. We mock the email you would get — consensus kept in, outrage left out.
          </p>

          <div className="mt-5">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-white/45">Topics</p>
            <div className="mt-2.5 flex flex-wrap gap-2">
              {TOPICS.map((topic) => {
                const active = selected.has(topic)
                return (
                  <button
                    key={topic}
                    type="button"
                    onClick={() => toggleTopic(topic)}
                    aria-pressed={active}
                    className={`rounded-full px-4 py-1.5 text-sm transition-colors ${
                      active ? 'bg-white text-black' : 'border text-white/70 hover:bg-white/10 hover:text-white'
                    }`}
                    style={active ? undefined : { borderColor: `${ACCENT}4D` }}
                  >
                    {topic}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="mt-5 grid grid-cols-2 gap-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-white/45">Rhythm</p>
              <div className="mt-2 space-y-2">
                {[
                  { id: 'weekly', label: 'Weekly • Fri 7am' },
                  { id: 'daily', label: 'Daily • 7am' },
                ].map((opt) => (
                  <label
                    key={opt.id}
                    className={`flex cursor-pointer items-center gap-2.5 rounded-xl border px-3.5 py-2.5 text-sm ${
                      cadence === opt.id ? 'border-white bg-white/[0.07] text-white' : 'border-white/10 text-white/60 hover:bg-white/5'
                    }`}
                  >
                    <input
                      type="radio"
                      name="cadence"
                      checked={cadence === opt.id}
                      onChange={() => setCadence(opt.id)}
                      className="accent-white"
                    />
                    {opt.label}
                  </label>
                ))}
              </div>
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-white/45">Length</p>
              <div className="mt-2 space-y-2">
                {['5 min', '7 min', '12 min'].map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => setLength(opt)}
                    aria-pressed={length === opt}
                    className={`w-full rounded-xl border px-3.5 py-2 text-sm transition-colors ${
                      length === opt ? 'border-white bg-white text-black' : 'border-white/10 text-white/60 hover:bg-white/5 hover:text-white'
                    }`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={() => {
              setSaved(true)
              window.setTimeout(() => setSaved(false), 2500)
            }}
            className="mt-6 w-full rounded-full bg-white px-6 py-2.5 text-sm font-medium text-black hover:bg-white/85"
          >
            {saved ? 'Saved (mock)' : `Save my ${cadence} briefing • ${length}`}
          </button>
          {saved && (
            <p role="status" className="mt-2 flex items-center gap-1.5 text-xs" style={{ color: ACCENT }}>
              <CheckCircle2 className="h-3.5 w-3.5" /> Preferences saved locally (frontend only).
            </p>
          )}
        </div>

        <div className="border-t border-white/10 bg-black/50 p-8 md:p-10 lg:border-l lg:border-t-0">
          <p className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-[0.14em] text-white/45">
            <MailOpen className="h-3.5 w-3.5" style={{ color: ACCENT }} />
            Live preview
          </p>
          <div className="mt-4 overflow-hidden rounded-xl border border-white/10 bg-white text-gray-900">
            <div className="border-b border-gray-100 px-5 py-4">
              <p className="text-xs text-gray-500">
                {cadence === 'weekly' ? 'Friday 7:00 • ' : 'Daily 7:00 • '}{length} • weaware.news
              </p>
              <p className="mt-1 font-display text-lg font-bold leading-tight">
                Your {cadence} Crosscheck — {previewStories.length} stories, 1 disagreement kept in
              </p>
            </div>
            <ul className="divide-y divide-gray-100">
              {previewStories.length === 0 ? (
                <li className="px-5 py-6 text-sm text-gray-500">Pick at least one topic to preview your email.</li>
              ) : (
                previewStories.map((s) => (
                  <li key={s.id} className="px-5 py-4">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">{s.topic}</p>
                    <p className="mt-1 text-sm font-semibold leading-snug">{s.title}</p>
                    <p className="mt-1 line-clamp-2 text-[13px] text-gray-600">{s.summary}</p>
                    <p className="mt-2 inline-block rounded-full bg-gray-900 px-2.5 py-0.5 text-[11px] font-medium text-white">
                      {s.consensus}% consensus
                    </p>
                  </li>
                ))
              )}
            </ul>
            <p className="bg-gray-50 px-5 py-3 text-[11px] text-gray-400">
              No spam, unsubscribe anytime. Sample uses fictional demo stories.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
