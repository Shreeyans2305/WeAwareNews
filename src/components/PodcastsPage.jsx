import { useEffect, useRef, useState } from 'react'
import { Pause, Play } from 'lucide-react'
import { episodes } from '../data/editions.js'
import { stories } from '../data/stories.js'
import Reveal from './Reveal.jsx'
import ListenAudiobook from './ListenAudiobook.jsx'

const ACCENT = '#00F0FF'

function useSimulatedProgress(playing, durationSeconds = 100) {
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    if (!playing) return
    const id = window.setInterval(() => {
      setElapsed((prev) => (prev + 1 >= durationSeconds ? 0 : prev + 1))
    }, 1000)
    return () => window.clearInterval(id)
  }, [playing, durationSeconds])
  useEffect(() => {
    if (!playing) setElapsed((v) => v)
  }, [playing])
  return [elapsed, setElapsed]
}

function formatTime(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

export default function PodcastsPage({ onListen, currentListenId, listeningPlaying }) {
  const [currentId, setCurrentId] = useState(episodes[0].id)
  const [playing, setPlaying] = useState(false)
  const [elapsed, setElapsed] = useSimulatedProgress(playing, 1080)
  const progressRef = useRef(null)

  const current = episodes.find((episode) => episode.id === currentId) ?? episodes[0]

  const selectEpisode = (id) => {
    if (id !== currentId) {
      setCurrentId(id)
      setElapsed(0)
      setPlaying(true)
    } else {
      setPlaying((prev) => !prev)
    }
  }

  const progress = Math.min(100, (elapsed / 1080) * 100)

  return (
    <div className="page-enter">
      <section className="perspective-stage px-6 pb-10 pt-14 md:px-12 md:pt-20">
        <div className="max-w-3xl">
          <p className="stagger-item eyebrow-kanit text-[12px] text-white/50" style={{ '--i': 0 }}>
            Podcasts
          </p>
          <h1 className="stagger-item mt-3 font-display text-5xl font-extrabold leading-[1.02] tracking-tight text-white md:text-6xl" style={{ '--i': 1 }}>
            <span className="display-3d display-3d-gradient">Listen to the disagreement, not just the headline.</span>
          </h1>
          <p className="stagger-item mt-4 max-w-xl font-display text-lg font-medium leading-relaxed text-white/70 md:text-xl" style={{ '--i': 2 }}>
            Two shows from the same newsroom. One briefs you in minutes, the other stays
            with one story until the sources stop contradicting each other.
          </p>
        </div>
      </section>

      <section className="px-6 pt-6 md:px-12">
        <ListenAudiobook
          stories={stories}
          currentId={currentListenId}
          playing={listeningPlaying}
          onSelect={(id) => onListen && onListen(id)}
          onPlayAll={() => onListen && onListen(stories[0].id)}
        />
      </section>

      <section className="px-6 md:px-12">
        <div className="stagger-item overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04]" style={{ '--i': 3 }}>
          <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="p-8 md:p-10">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setPlaying((prev) => !prev)}
                  aria-label={playing ? `Pause ${current.title}` : `Play ${current.title}`}
                  aria-pressed={playing}
                  className="flex h-14 w-14 items-center justify-center rounded-full bg-white text-black transition-transform hover:scale-105"
                >
                  {playing ? <Pause className="h-6 w-6" /> : <Play className="ml-0.5 h-6 w-6" />}
                </button>
                <div
                  aria-hidden="true"
                  className={`flex h-6 items-end gap-1 ${playing ? '' : 'eq-paused'}`}
                >
                  <span className="eq-bar w-1 rounded-full" style={{ height: '100%', backgroundColor: ACCENT }} />
                  <span className="eq-bar w-1 rounded-full" style={{ height: '100%', backgroundColor: ACCENT }} />
                  <span className="eq-bar w-1 rounded-full" style={{ height: '100%', backgroundColor: ACCENT }} />
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.14em] text-white/50">{current.show}</p>
                  <p className="text-sm text-white/70">{playing ? 'Now playing' : 'Paused'}</p>
                </div>
              </div>

              <h2 className="mt-5 font-display text-3xl font-extrabold tracking-tight text-white md:text-4xl">
                {current.title}
              </h2>
              <p className="mt-3 leading-relaxed text-white/60">{current.description}</p>

              <div className="mt-6">
                <div className="flex items-center justify-between text-xs text-white/50">
                  <span>{formatTime(elapsed)}</span>
                  <span>{current.duration}</span>
                </div>
                <div
                  ref={progressRef}
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.round(progress)}
                  aria-label={`Progress for ${current.title}`}
                  className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10"
                >
                  <div
                    className="h-full rounded-full transition-[width] duration-500"
                    style={{
                      width: `${progress}%`,
                      background: `linear-gradient(to right, rgba(0,240,255,0.55), ${ACCENT})`,
                    }}
                  />
                </div>
                <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-white/50">
                  <span className="rounded-full border border-white/10 bg-black/40 px-3 py-1">{current.topic}</span>
                  <span className="rounded-full border border-white/10 bg-black/40 px-3 py-1">{current.date}</span>
                  <span className="rounded-full border border-white/10 bg-black/40 px-3 py-1">Sources linked in notes</span>
                </div>
              </div>
            </div>

            <div className="border-t border-white/10 bg-black/50 lg:border-l lg:border-t-0">
              <ul className="divide-y divide-white/10">
                {episodes.map((episode) => {
                  const active = episode.id === currentId
                  const isPlayingThis = active && playing
                  return (
                    <li key={episode.id}>
                      <button
                        type="button"
                        onClick={() => selectEpisode(episode.id)}
                        aria-current={active ? 'true' : undefined}
                        className={`group flex w-full items-center gap-4 p-5 text-left transition-colors ${
                          active ? 'bg-white/[0.06]' : 'hover:bg-white/[0.04]'
                        }`}
                      >
                        <span
                          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full border transition-colors ${
                            active
                              ? 'border-transparent bg-white text-black'
                              : 'border-white/15 text-white group-hover:border-white/30'
                          }`}
                        >
                          {isPlayingThis ? (
                            <Pause className="h-4 w-4" />
                          ) : (
                            <Play className="ml-0.5 h-4 w-4" />
                          )}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium text-white">
                            {episode.title}
                          </span>
                          <span className="mt-1 block text-xs text-white/45">
                            {episode.show} • {episode.duration} • {episode.date}
                          </span>
                        </span>
                        {active && (
                          <span
                            className="h-1.5 w-1.5 shrink-0 rounded-full"
                            style={{ backgroundColor: ACCENT }}
                            aria-hidden="true"
                          />
                        )}
                      </button>
                    </li>
                  )
                })}
              </ul>
            </div>
          </div>
        </div>
      </section>

      <Reveal className="px-6 py-12 md:px-12">
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-8">
            <h2 className="font-display text-2xl font-extrabold tracking-tight text-white">WeAware Daily Brief</h2>
            <p className="mt-2 text-sm leading-relaxed text-white/60">
              Weekday mornings. Three stories, consensus scores read aloud, and the one
              flagged claim you should not repeat at lunch.
            </p>
            <p className="mt-4 text-xs uppercase tracking-[0.14em] text-white/40">New episodes weekday mornings</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-8">
            <h2 className="font-display text-2xl font-extrabold tracking-tight text-white">The Disagreement</h2>
            <p className="mt-2 text-sm leading-relaxed text-white/60">
              Weekly. One contested story, all source stances on the table, and what would
              need to change for consensus to move.
            </p>
            <p className="mt-4 text-xs uppercase tracking-[0.14em] text-white/40">New episodes every Thursday</p>
          </div>
        </div>
      </Reveal>
    </div>
  )
}
