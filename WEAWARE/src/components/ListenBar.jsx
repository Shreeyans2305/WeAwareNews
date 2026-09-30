import { useEffect, useState } from 'react'
import { ChevronUp, Pause, Play, RotateCcw, RotateCw, SkipBack, SkipForward, X } from 'lucide-react'

function formatTime(totalSeconds) {
  const m = Math.floor(totalSeconds / 60)
  const s = totalSeconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

export function listenMinsFor(story) {
  return (story.readMins ?? 4) + 4
}

export default function ListenBar({ story, queue = [], playing, onToggle, onClose, onSelect, onNext, onPrev }) {
  const total = listenMinsFor(story) * 60
  const [elapsed, setElapsed] = useState(0)
  const [speed, setSpeed] = useState(1)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    setElapsed(0)
  }, [story.id])

  useEffect(() => {
    if (!playing) return
    const id = window.setInterval(() => {
      setElapsed((prev) => (prev + 1 >= total ? 0 : prev + 1))
    }, 1000 / speed)
    return () => window.clearInterval(id)
  }, [playing, total, speed])

  if (!story) return null

  const progress = Math.min(100, (elapsed / total) * 100)
  const cycleSpeed = () => setSpeed((s) => (s === 1 ? 1.25 : s === 1.25 ? 1.5 : 1))
  const seekBy = (delta) => setElapsed((v) => Math.max(0, Math.min(total, v + delta)))

  return (
    <div className="fixed inset-x-0 bottom-0 z-40 px-3 pb-3 md:px-6 md:pb-5" role="region" aria-label="Audiobook player">
      <div className="t-card mx-auto max-w-4xl overflow-hidden rounded-2xl border">
        <div className="flex items-center gap-3 px-4 pt-3 md:px-5">
          <div aria-hidden="true" className={`flex h-5 items-end gap-0.5 ${playing ? '' : 'eq-paused'}`}>
            <span className="eq-bar w-1 rounded-full" style={{ height: '100%' }} />
            <span className="eq-bar w-1 rounded-full" style={{ height: '100%' }} />
            <span className="eq-bar w-1 rounded-full" style={{ height: '100%' }} />
          </div>
          <p className="t-muted text-[11px] font-semibold uppercase tracking-[0.18em]">Audiobook • AI voice • {speed}x</p>
          <div className="ml-auto flex items-center gap-1">
            <button type="button" onClick={() => setExpanded((v) => !v)} aria-expanded={expanded} aria-label={expanded ? 'Collapse queue' : 'Expand queue'} className="t-btn-outline rounded-full p-2">
              <ChevronUp className={`h-4 w-4 ${expanded ? 'rotate-180' : ''}`} />
            </button>
            <button type="button" onClick={onClose} aria-label="Close player" className="t-btn-outline rounded-full p-2">
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="flex items-center gap-3 px-4 pb-2 md:gap-4 md:px-5">
          <button type="button" onClick={onPrev} aria-label="Previous story" className="t-btn-outline hidden rounded-full p-2 sm:block">
            <SkipBack className="h-4 w-4" />
          </button>
          <button type="button" onClick={() => seekBy(-15)} aria-label="Back 15 seconds" className="t-btn-outline rounded-full p-2">
            <RotateCcw className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onToggle}
            aria-label={playing ? `Pause ${story.title}` : `Play ${story.title}`}
            aria-pressed={playing}
            className="t-btn-primary flex h-12 w-12 shrink-0 items-center justify-center rounded-full"
          >
            {playing ? <Pause className="h-5 w-5" /> : <Play className="ml-0.5 h-5 w-5" />}
          </button>
          <button type="button" onClick={() => seekBy(15)} aria-label="Forward 15 seconds" className="t-btn-outline rounded-full p-2">
            <RotateCw className="h-4 w-4" />
          </button>
          <button type="button" onClick={onNext} aria-label="Next story" className="t-btn-outline hidden rounded-full p-2 sm:block">
            <SkipForward className="h-4 w-4" />
          </button>

          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{story.title}</p>
            <p className="t-muted truncate text-xs">{story.topic} • {listenMinsFor(story)} min listen • {story.consensus}% consensus</p>
          </div>

          <button type="button" onClick={cycleSpeed} aria-label={`Playback speed ${speed}x, activate to change`} className="t-btn-outline shrink-0 rounded-full px-3 py-1.5 text-xs font-medium">
            {speed}x
          </button>
        </div>

        <div className="px-4 pb-3 md:px-5 md:pb-4">
          <div className="t-muted flex items-center justify-between text-[11px]">
            <span>{formatTime(Math.floor(elapsed))}</span>
            <span>{formatTime(total)}</span>
          </div>
          <div
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(progress)}
            aria-label={`Listening progress for ${story.title}`}
            className="t-card mt-1.5 h-1.5 cursor-pointer overflow-hidden rounded-full border"
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect()
              const ratio = (e.clientX - rect.left) / rect.width
              setElapsed(Math.floor(ratio * total))
            }}
          >
            <div className="h-full rounded-full" style={{ width: `${progress}%`, background: 'var(--fg)' }} />
          </div>
        </div>

        {expanded && (
          <div className="t-border max-h-56 overflow-y-auto border-t">
            <p className="t-faint px-4 pt-3 text-[11px] font-semibold uppercase tracking-[0.18em] md:px-5">Up next — today’s audiobook queue</p>
            <ul className="t-border divide-y">
              {queue.slice(0, 6).map((item) => {
                const active = item.id === story.id
                return (
                  <li key={item.id}>
                    <button type="button" onClick={() => onSelect(item.id)} aria-current={active ? 'true' : undefined} className="flex w-full items-center gap-3 px-4 py-2.5 text-left md:px-5">
                      <span className={active ? 't-btn-primary flex h-8 w-8 shrink-0 items-center justify-center rounded-full' : 't-btn-outline flex h-8 w-8 shrink-0 items-center justify-center rounded-full'}>
                        {active && playing ? <Pause className="h-3.5 w-3.5" /> : <Play className="ml-0.5 h-3.5 w-3.5" />}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[13px] font-medium">{item.title}</span>
                        <span className="t-muted block text-[11px]">{item.topic} • {listenMinsFor(item)} min</span>
                      </span>
                      {active && <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: 'var(--fg)' }} />}
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
