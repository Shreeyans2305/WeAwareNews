import { Headphones, Pause, Play } from 'lucide-react'
import { listenMinsFor } from './ListenBar.jsx'

const ACCENT = '#00F0FF'

export default function ListenAudiobook({ stories, currentId, playing, onSelect, onPlayAll }) {
  const totalMins = stories.slice(0, 5).reduce((sum, s) => sum + listenMinsFor(s), 0)

  return (
    <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04]">
      <div className="flex flex-wrap items-center gap-4 p-6 md:p-8">
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-white text-black">
          <Headphones className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: ACCENT }}>
            Audiobook • Today’s news on the go
          </p>
          <h2 className="mt-1 font-display text-2xl font-extrabold tracking-tight text-white">
            Listen to the top 5, back to back
          </h2>
          <p className="mt-1 text-sm text-white/55">
            {totalMins} min total • AI-read cross-checks • 15s skip • 1x–1.5x speed • mock audio
          </p>
        </div>
        <button
          type="button"
          onClick={onPlayAll}
          className="rounded-full bg-white px-6 py-2.5 text-sm font-medium text-black hover:bg-white/85"
        >
          Play all
        </button>
      </div>
      <ul className="divide-y divide-white/10 border-t border-white/10">
        {stories.slice(0, 5).map((story, idx) => {
          const active = story.id === currentId
          const isPlayingThis = active && playing
          return (
            <li key={story.id}>
              <button
                type="button"
                onClick={() => onSelect(story.id)}
                aria-current={active ? 'true' : undefined}
                className={`flex w-full items-center gap-4 px-6 py-4 text-left transition-colors md:px-8 ${
                  active ? 'bg-white/[0.06]' : 'hover:bg-white/[0.03]'
                }`}
              >
                <span className="w-6 shrink-0 font-mono text-xs text-white/35">{String(idx + 1).padStart(2, '0')}</span>
                <span
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full border ${
                    active ? 'border-transparent bg-white text-black' : 'border-white/15 text-white'
                  }`}
                >
                  {isPlayingThis ? <Pause className="h-4 w-4" /> : <Play className="ml-0.5 h-4 w-4" />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-white">{story.title}</span>
                  <span className="mt-0.5 block text-xs text-white/45">
                    {story.topic} • {listenMinsFor(story)} min listen • {story.consensus}% consensus
                  </span>
                </span>
                {active && <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ backgroundColor: ACCENT }} />}
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
