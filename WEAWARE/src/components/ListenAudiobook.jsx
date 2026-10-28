import { Headphones, Pause, Play } from 'lucide-react'
import { listenMinsFor } from './ListenBar.jsx'

export default function ListenAudiobook({ stories, currentId, playing, onSelect, onPlayAll }) {
  const list = Array.isArray(stories) ? stories.slice(0, 5) : []
  const totalMins = list.reduce((sum, s) => sum + listenMinsFor(s), 0)

  if (list.length === 0) {
    return (
      <div className="t-card t-border border p-8 text-center md:p-10">
        <p className="kicker">Audiobook</p>
        <h2 className="headline-serif mt-3 text-2xl">No stories to play yet.</h2>
        <p className="t-muted font-body-serif mt-2 text-[15px] leading-relaxed">
          New crosschecks land each morning. Browse the feed to find a story to hear.
        </p>
      </div>
    )
  }

  return (
    <div className="t-card t-border border">
      <div className="rule-thick" aria-hidden="true" />
      <div className="flex flex-wrap items-center gap-4 px-6 pt-5 md:px-8">
        <span className="t-btn-primary flex h-12 w-12 items-center justify-center rounded-full" aria-hidden="true">
          <Headphones className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="kicker">Audiobook · Today on the go</p>
          <h2 className="headline-serif mt-1.5 text-2xl leading-tight md:text-[1.7rem]">Hear the top 5, back to back</h2>
          <p className="byline mt-1.5">About {totalMins} min total · Audio is generated when you start listening</p>
        </div>
        <button type="button" onClick={onPlayAll} className="t-btn-primary px-6 py-2.5 text-sm font-medium">
          Play all
        </button>
      </div>
      <ul className="t-border mt-5 divide-y border-t">
        {list.map((story, idx) => {
          const active = story.id === currentId
          const isPlayingThis = active && playing
          return (
            <li key={story.id}>
              <button type="button" onClick={() => onSelect(story.id)} aria-current={active ? 'true' : undefined} className="flex w-full items-center gap-4 px-6 py-4 text-left md:px-8">
                <span className="t-faint w-6 shrink-0 font-mono text-xs">{String(idx + 1).padStart(2, '0')}</span>
                <span className={active ? 't-btn-primary flex h-10 w-10 shrink-0 items-center justify-center rounded-full' : 't-btn-outline flex h-10 w-10 shrink-0 items-center justify-center rounded-full'}>
                  {isPlayingThis ? <Pause className="h-4 w-4" /> : <Play className="ml-0.5 h-4 w-4" />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{story.title}</span>
                  <span className="t-muted mt-0.5 block text-xs">{story.topic} · {listenMinsFor(story)} min listen · {story.consensus}% consensus</span>
                </span>
                {active && <span className="signal-dot h-1.5 w-1.5 shrink-0 rounded-full" aria-hidden="true" />}
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
