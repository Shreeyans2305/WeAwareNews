import { useEffect, useState } from 'react'
import { MailOpen, Sparkles } from 'lucide-react'
import { TOPICS } from '../data/stories.js'

export default function NewsletterPersonalizer({ stories = [], topics = [] }) {
  const [selected, setSelected] = useState(() => new Set(['AI', 'Good News']))
  const [cadence, setCadence] = useState('weekly')

  useEffect(() => {
    if (!stories.length) return
    setSelected((current) => {
      if (stories.some((story) => current.has(story.topic))) return current
      return new Set(stories.slice(0, 3).map((story) => story.topic))
    })
  }, [stories])

  const toggleTopic = (topic) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(topic)) next.delete(topic)
      else next.add(topic)
      return next
    })
  }

  const previewStories = stories.filter((s) => selected.has(s.topic)).slice(0, 3)

  return (
    <div className="t-card overflow-hidden rounded-2xl border">
      <div className="grid grid-cols-1 lg:grid-cols-2">
        <div className="p-8 md:p-10">
          <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.18em]">
            <Sparkles className="h-3.5 w-3.5" />
            Personalised email preview
          </p>
          <h2 className="mt-3 font-display text-3xl font-extrabold tracking-tight">Your briefing, tuned to you</h2>
          <p className="t-muted mt-2 text-sm leading-relaxed">Pick topics once. Preview the email you would get, with consensus kept in and outrage left out.</p>

          <div className="mt-5">
            <p className="t-muted text-xs font-medium uppercase tracking-[0.14em]">Topics</p>
            <div className="mt-2.5 flex flex-wrap gap-2">
              {(topics.length ? topics : TOPICS).map((topic) => {
                const active = selected.has(topic)
                return (
                  <button key={topic} type="button" onClick={() => toggleTopic(topic)} aria-pressed={active} className={active ? 't-btn-primary rounded-full px-4 py-1.5 text-sm' : 't-btn-outline rounded-full px-4 py-1.5 text-sm'}>
                    {topic}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="mt-5 grid grid-cols-2 gap-3">
            <div>
              <p className="t-muted text-xs font-medium uppercase tracking-[0.14em]">Rhythm</p>
              <div className="mt-2 space-y-2">
                {[
                  { id: 'weekly', label: 'Weekly' },
                  { id: 'daily', label: 'Daily' },
                ].map((opt) => (
                  <label key={opt.id} className={cadence === opt.id ? 't-btn-primary flex cursor-pointer items-center gap-2.5 rounded-xl px-3.5 py-2.5 text-sm' : 't-btn-outline flex cursor-pointer items-center gap-2.5 rounded-xl px-3.5 py-2.5 text-sm'}>
                    <input type="radio" name="cadence" checked={cadence === opt.id} onChange={() => setCadence(opt.id)} />
                    {opt.label}
                  </label>
                ))}
              </div>
            </div>
          </div>
          <p className="t-muted mt-6 text-sm">This is a preview. Use the subscription settings above to save your daily or weekly delivery.</p>
        </div>

        <div className="t-border t-card border-t p-8 md:p-10 lg:border-l lg:border-t-0">
          <p className="t-muted flex items-center gap-1.5 text-xs font-medium uppercase tracking-[0.14em]">
            <MailOpen className="h-3.5 w-3.5" />
            Live preview
          </p>
          <div className="t-card mt-4 overflow-hidden rounded-xl border">
            <div className="t-border border-b px-5 py-4">
              <p className="t-muted text-xs">{cadence === 'weekly' ? 'Weekly' : 'Daily'} • weaware-3504c.web.app</p>
              <p className="mt-1 font-display text-lg font-bold leading-tight">Your {cadence} Crosscheck, {previewStories.length} stories, 1 disagreement kept in</p>
            </div>
            <ul className="t-border divide-y">
              {previewStories.length === 0 ? (
                <li className="t-muted px-5 py-6 text-sm">{selected.size ? 'No stories in these topics yet. Your briefing will fill in as new coverage arrives.' : 'Choose a topic to preview your email.'}</li>
              ) : (
                previewStories.map((s) => (
                  <li key={s.id} className="px-5 py-4">
                    <p className="t-faint text-[11px] font-semibold uppercase tracking-wider">{s.topic}</p>
                    <p className="mt-1 text-sm font-semibold leading-snug">{s.title}</p>
                    <p className="t-muted mt-1 line-clamp-2 text-[13px]">{s.summary}</p>
                    <p className="t-btn-primary mt-2 inline-block rounded-full px-2.5 py-0.5 text-[11px] font-medium">{s.consensus}% consensus</p>
                  </li>
                ))
              )}
            </ul>
            <p className="t-muted px-5 py-3 text-[11px]">No spam, unsubscribe anytime. Preview uses the stories shown on this page.</p>
          </div>
        </div>
      </div>
    </div>
  )
}
