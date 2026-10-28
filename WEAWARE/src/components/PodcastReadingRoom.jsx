import { useEffect, useRef, useState } from 'react'
import { Heart, Pause, Play, SkipBack, SkipForward } from 'lucide-react'

function formatDuration(totalSeconds = 0) {
  const mins = Math.floor(totalSeconds / 60)
  return `${mins} min`
}

function displayDate(value) {
  if (!value) return 'Recently published'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Recently published' : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(date)
}

function formatTime(totalSeconds) {
  const safeSeconds = Number.isFinite(totalSeconds) ? Math.max(0, Math.floor(totalSeconds)) : 0
  const m = Math.floor(safeSeconds / 60)
  const s = safeSeconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

function initialFor(title = 'W') {
  const clean = title.trim()
  return clean.length > 0 ? clean[0].toUpperCase() : 'W'
}

export function PodcastReadingRoom({ episodes = [], selectedEpisodeId, onEpisodeSelect }) {
  const audioRef = useRef(null)
  const [activeIndex, setActiveIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [duration, setDuration] = useState(0)
  const [liked, setLiked] = useState({})

  const safeEpisodes = episodes.length > 0 ? episodes : []
  const hasEpisodes = safeEpisodes.length > 0
  const activeTrack = hasEpisodes ? safeEpisodes[Math.min(activeIndex, safeEpisodes.length - 1)] : null
  const totalSeconds = duration || activeTrack?.durationSeconds || 0
  const progress = totalSeconds > 0 ? Math.min(100, (elapsed / totalSeconds) * 100) : 0

  useEffect(() => {
    setElapsed(0)
    setDuration(0)
    audioRef.current?.load()
  }, [activeIndex])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio || !hasEpisodes || !activeTrack?.audioUrl) return
    if (playing) audio.play().catch(() => setPlaying(false))
    else audio.pause()
  }, [playing, activeTrack?.audioUrl, hasEpisodes])

  useEffect(() => {
    if (!selectedEpisodeId) return
    const index = safeEpisodes.findIndex((episode) => episode.id === selectedEpisodeId)
    if (index >= 0) {
      setActiveIndex(index)
      setPlaying(true)
    }
  }, [selectedEpisodeId, episodes])

  const selectEpisode = (index) => {
    if (index !== activeIndex) {
      setActiveIndex(index)
      setElapsed(0)
      setPlaying(true)
    } else {
      setPlaying((p) => !p)
    }
    if (onEpisodeSelect && safeEpisodes[index]) onEpisodeSelect(safeEpisodes[index].id)
  }

  const step = (dir) => {
    if (!hasEpisodes) return
    const next = (activeIndex + dir + safeEpisodes.length) % safeEpisodes.length
    selectEpisode(next)
  }

  const seekTo = (seconds) => {
    const audio = audioRef.current
    if (audio && Number.isFinite(audio.duration)) audio.currentTime = Math.max(0, Math.min(audio.duration, seconds))
  }

  const toggleLike = () => {
    if (!activeTrack) return
    setLiked((prev) => ({ ...prev, [activeTrack.id]: !prev[activeTrack.id] }))
  }

  if (!hasEpisodes) {
    return (
      <div className="t-card t-border border p-8 text-center md:p-10">
        <p className="kicker">Listening desk</p>
        <h2 className="headline-serif mt-3 text-2xl">No episodes yet.</h2>
        <p className="t-muted font-body-serif mt-2 text-[15px] leading-relaxed">
          New approved, narrated episodes will appear here after editorial review.
        </p>
      </div>
    )
  }

  return (
    <div className="t-card t-border border">
      <div className="rule-thick" aria-hidden="true" />
      <div className="flex flex-wrap items-center gap-3 px-6 pt-5 md:px-8">
        <p className="kicker">Listening desk</p>
        <span className="stamp" aria-label="Show: WeAware Daily Brief">WeAware Daily Brief</span>
        <p className="t-faint ml-auto text-xs">AI-narrated audio</p>
      </div>

      <div className="grid min-w-0 grid-cols-1 gap-0 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
        <div className="min-w-0 p-6 md:p-8">
          <div className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-4 gap-y-4">
            <div
              aria-hidden="true"
              className="paper-grain t-border flex h-20 w-20 shrink-0 items-center justify-center border"
            >
              <span className="font-serif-news text-4xl font-black leading-none">{initialFor(activeTrack.title)}</span>
            </div>
            <div className="min-w-0">
              <p className="t-muted text-[11px] font-semibold uppercase tracking-[0.22em]">Now playing</p>
              <p className="byline mt-1.5">
                {activeTrack.topic} · {formatDuration(totalSeconds)} · {displayDate(activeTrack.date)}
              </p>
            </div>
            <button
              type="button"
              onClick={toggleLike}
              aria-label={liked[activeTrack.id] ? 'Unlike episode' : 'Like episode'}
              aria-pressed={!!liked[activeTrack.id]}
              className="t-btn-outline flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
            >
              <Heart className="h-4 w-4" fill={liked[activeTrack.id] ? 'currentColor' : 'none'} />
            </button>
            <div className="col-span-3 min-w-0">
              <h3 className="headline-serif break-words text-2xl leading-tight md:text-[1.7rem]">
                {activeTrack.title}
              </h3>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px]">
                <span className="t-btn-outline px-3 py-1">{activeTrack.topic}</span>
                <span className="t-btn-outline px-3 py-1">{displayDate(activeTrack.date)}</span>
                <span className="t-btn-outline px-3 py-1">Sources in notes</span>
              </div>
            </div>
          </div>

          <p className="t-muted font-body-serif mt-5 text-[15px] leading-relaxed">{activeTrack.description}</p>
          {activeTrack.sourceUrls?.length ? (
            <details className="t-border mt-4 border-t pt-3">
              <summary className="t-muted cursor-pointer text-xs font-semibold">Sources and show notes</summary>
              <ul className="mt-2 space-y-1.5">
                {activeTrack.sourceUrls.map((url) => (
                  <li key={url} className="truncate text-xs">
                    <a className="underline underline-offset-2" href={url} target="_blank" rel="noreferrer">{url}</a>
                  </li>
                ))}
              </ul>
            </details>
          ) : null}

          <div className="mt-6">
            <div className="t-muted flex items-center justify-between text-xs font-medium">
              <span>{formatTime(elapsed)}</span>
              <span>{formatTime(totalSeconds)}</span>
            </div>
            <div
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(progress)}
              aria-label={`Progress for ${activeTrack.title}`}
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'ArrowRight') seekTo(elapsed + 15)
                if (e.key === 'ArrowLeft') seekTo(elapsed - 15)
              }}
              onClick={(e) => {
                const rect = e.currentTarget.getBoundingClientRect()
                const ratio = (e.clientX - rect.left) / rect.width
                seekTo(ratio * totalSeconds)
              }}
              className="t-border mt-2 h-1.5 w-full cursor-pointer overflow-hidden border"
            >
              <div className="h-full" style={{ width: `${progress}%`, background: 'var(--fg)' }} />
            </div>
          </div>

          <div className="mt-6 flex items-center gap-3">
            <button
              type="button"
              onClick={() => step(-1)}
              aria-label="Previous episode"
              className="t-btn-outline flex h-10 w-10 items-center justify-center rounded-full"
            >
              <SkipBack className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => setPlaying((p) => !p)}
              aria-label={playing ? `Pause ${activeTrack.title}` : `Play ${activeTrack.title}`}
              aria-pressed={playing}
              className="t-btn-primary flex h-12 w-12 items-center justify-center rounded-full"
            >
              {playing ? <Pause className="h-5 w-5" /> : <Play className="ml-0.5 h-5 w-5" />}
            </button>
              <button
              type="button"
              onClick={() => step(1)}
              aria-label="Next episode"
              className="t-btn-outline flex h-10 w-10 items-center justify-center rounded-full"
            >
              <SkipForward className="h-4 w-4" />
            </button>
            <div aria-hidden="true" className={`ml-2 flex h-5 items-end gap-0.5 ${playing ? '' : 'eq-paused'}`}>
              <span className="eq-bar w-1" style={{ height: '100%' }} />
              <span className="eq-bar w-1" style={{ height: '100%' }} />
              <span className="eq-bar w-1" style={{ height: '100%' }} />
            </div>
            <span className="t-faint text-[11px] uppercase tracking-[0.18em]">
              {playing ? 'Playing' : 'Paused'}
            </span>
          </div>

          <div className="mt-6 flex flex-col gap-2 sm:flex-row">
            <button
              type="button"
              onClick={() => selectEpisode(0)}
              className="t-btn-primary px-6 py-2.5 text-sm font-medium"
            >
              Play latest brief
            </button>
            <button
              type="button"
              onClick={() => document.getElementById('podcast-episodes')?.scrollIntoView({ behavior: 'smooth' })}
              className="t-btn-outline px-6 py-2.5 text-sm font-medium"
            >
              Browse episodes
            </button>
          </div>
        </div>

        <div className="t-border min-w-0 border-t lg:border-l lg:border-t-0">
          <p className="t-faint px-6 pt-5 text-[11px] font-semibold uppercase tracking-[0.18em] md:px-8">
            Episode index
          </p>
          <ul id="podcast-episodes" className="t-border mt-3 divide-y border-t">
            {safeEpisodes.map((track, index) => {
              const isActive = index === activeIndex
              const isPlayingThis = isActive && playing
              return (
                <li key={track.id}>
                  <button
                    type="button"
                    onClick={() => selectEpisode(index)}
                    aria-pressed={isActive}
                    aria-current={isActive ? 'true' : undefined}
                    className="flex w-full min-w-0 items-center gap-3 px-4 py-4 text-left sm:gap-4 sm:px-6 md:px-8"
                    style={isActive ? { boxShadow: 'inset 2px 0 0 var(--fg)' } : undefined}
                  >
                    <span className="t-faint w-6 shrink-0 font-mono text-xs">{String(index + 1).padStart(2, '0')}</span>
                    <span className={isActive ? 't-btn-primary flex h-10 w-10 shrink-0 items-center justify-center rounded-full' : 't-btn-outline flex h-10 w-10 shrink-0 items-center justify-center rounded-full'}>
                      {isPlayingThis ? <Pause className="h-4 w-4" /> : <Play className="ml-0.5 h-4 w-4" />}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block break-words text-sm font-medium leading-snug">{track.title}</span>
                      <span className="t-muted mt-0.5 block truncate text-xs">
                        {track.topic} · {formatDuration(track.durationSeconds)}
                      </span>
                    </span>
                    {isActive && <span className="signal-dot h-1.5 w-1.5 shrink-0 rounded-full" aria-hidden="true" />}
                  </button>
                </li>
              )
            })}
          </ul>
          <div className="rule-thin mx-6 mb-6 md:mx-8" aria-hidden="true" />
        </div>
      </div>
      {activeTrack?.audioUrl ? (
        <audio
          ref={audioRef}
          src={activeTrack.audioUrl}
          preload="metadata"
          onLoadedMetadata={(event) => setDuration(event.currentTarget.duration || 0)}
          onDurationChange={(event) => setDuration(event.currentTarget.duration || 0)}
          onTimeUpdate={(event) => setElapsed(event.currentTarget.currentTime || 0)}
          onEnded={() => setPlaying(false)}
          onError={() => setPlaying(false)}
        />
      ) : null}
    </div>
  )
}

export default PodcastReadingRoom
