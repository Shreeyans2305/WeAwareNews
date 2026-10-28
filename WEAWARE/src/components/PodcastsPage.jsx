import { useEffect, useState } from 'react'
import { CheckCircle2, Copy, Mic, Scissors } from 'lucide-react'
import { API_BASE, fetchPodcastEpisodes } from '../lib/api.js'
import Reveal from './Reveal.jsx'
import ListenAudiobook from './ListenAudiobook.jsx'
import { PodcastReadingRoom } from './PodcastReadingRoom.jsx'
import PodcastEditorialReview from './PodcastEditorialReview.jsx'

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

function FollowFolio({ onPlayLatest }) {
  const [copied, setCopied] = useState(false)
  const feedUrl = `${API_BASE}/podcasts/feed.xml`

  const copyFeed = async () => {
    try {
      await navigator.clipboard.writeText(feedUrl)
    } catch {
      const ta = document.createElement('textarea')
      ta.value = feedUrl
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    setCopied(true)
    window.setTimeout(() => setCopied(false), 2000)
  }

  const scrollToDesk = () => {
    if (onPlayLatest) {
      onPlayLatest()
      return
    }
    document.getElementById('podcast-desk')?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <div className="border t-border p-1.5">
      <div className="t-card t-border border px-6 py-10 text-center md:px-12 md:py-12">
        <p className="kicker">Follow the shows</p>
        <h2 className="headline-serif mx-auto mt-3 max-w-2xl text-3xl md:text-4xl">
          Take the briefing with you.
        </h2>
        <p className="t-muted font-body-serif mx-auto mt-3 max-w-xl text-[15px] leading-relaxed">
          Subscribe in your podcast app, or play a published briefing here. New episodes appear in the feed after editorial review.
        </p>
        <div className="mx-auto mt-6 flex max-w-xl flex-col gap-2 sm:flex-row sm:items-center sm:justify-center">
          <button
            type="button"
            onClick={copyFeed}
            className="t-btn-primary flex items-center justify-center gap-2 px-6 py-2.5 text-sm font-medium"
          >
            {copied ? <CheckCircle2 className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            {copied ? 'Copied' : 'Copy feed URL'}
          </button>
          <button
            type="button"
            onClick={scrollToDesk}
            className="t-btn-outline px-6 py-2.5 text-sm font-medium"
          >
            Play latest brief
          </button>
        </div>
        {copied ? (
          <p role="status" className="t-muted mt-3 text-xs">Feed URL copied. Paste it in your podcast app.</p>
        ) : (
          <p className="t-faint mt-3 text-xs">Public RSS feed · No signup needed to listen.</p>
        )}
      </div>
    </div>
  )
}

export default function PodcastsPage({ onListen, currentListenId, listeningPlaying, stories = [] }) {
  const [episodes, setEpisodes] = useState([])
  const [selectedEpisodeId, setSelectedEpisodeId] = useState(null)
  const [episodesLoading, setEpisodesLoading] = useState(true)
  const [episodesError, setEpisodesError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    fetchPodcastEpisodes(controller.signal)
      .then((result) => setEpisodes(result.episodes || []))
      .catch((error) => {
        if (error.name !== 'AbortError') setEpisodesError('Podcast episodes are temporarily unavailable.')
      })
      .finally(() => setEpisodesLoading(false))
    return () => controller.abort()
  }, [])

  const scrollToDesk = () => {
    document.getElementById('podcast-desk')?.scrollIntoView({ behavior: 'smooth' })
  }

  const handlePublishedEpisodes = (nextEpisodes, episodeId) => {
    setEpisodes(nextEpisodes)
    setSelectedEpisodeId(episodeId)
    scrollToDesk()
  }

  return (
    <div className="page-enter">
      <section className="px-6 pb-8 pt-14 md:px-12 md:pt-20">
        <div className="mx-auto max-w-6xl">
          <p className="stagger-item kicker" style={{ '--i': 0 }}>Podcasts</p>
          <h1 className="stagger-item masthead-title mt-3 text-5xl md:text-7xl" style={{ '--i': 1 }}>
            Listen to the disagreement, not just the headline.
          </h1>
          <p className="stagger-item t-muted font-body-serif mt-4 max-w-2xl text-[17px] leading-relaxed md:text-lg" style={{ '--i': 2 }}>
            Two shows from the same newsroom. One briefs you in minutes, the other stays with one story until the
            sources stop contradicting each other.
          </p>
          <div className="stagger-item rule-double-wrap mt-8" style={{ '--i': 3 }} aria-hidden="true">
            <div className="rule-thick" />
            <div className="rule-thin" />
          </div>
          <p className="stagger-item byline mt-3" style={{ '--i': 4 }}>
            Published episodes · AI narration · Editorial review and sources included
          </p>
        </div>
      </section>

      <section aria-label="Choose your show" className="px-6 py-10 md:px-12">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <SectionHeader index="B" title="Choose your show" blurb="Two rhythms. Pick the one that fits your morning." />
          </Reveal>
          <div className="t-border mt-8 grid grid-cols-1 gap-0 border md:grid-cols-2">
            <article className="stagger-item p-6 md:p-8" style={{ '--i': 0 }}>
              <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em]">
                <Mic className="h-4 w-4" aria-hidden="true" />
                Weekday mornings
              </p>
              <h2 className="headline-serif mt-2 text-3xl">WeAware Daily Brief</h2>
              <p className="t-muted mt-1 text-xs font-semibold uppercase tracking-[0.14em]">Daily · about 10 min</p>
              <p className="t-muted font-body-serif mt-3 text-[15px] leading-relaxed">
                Three stories, consensus scores read aloud, and the one flagged claim to read twice before lunch.
              </p>
              <p className="t-faint mt-4 text-xs uppercase tracking-[0.14em]">New episodes weekday mornings</p>
            </article>
            <article className="stagger-item t-border border-t p-6 md:border-l md:border-t-0 md:p-8" style={{ '--i': 1 }}>
              <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em]">
                <Mic className="h-4 w-4" aria-hidden="true" />
                Weekly discussion
              </p>
              <h2 className="headline-serif mt-2 text-3xl">The Disagreement</h2>
              <p className="t-muted mt-1 text-xs font-semibold uppercase tracking-[0.14em]">Weekly, 21 to 24 min</p>
              <p className="t-muted font-body-serif mt-3 text-[15px] leading-relaxed">
                One contested story, all source stances on the table, and what would need to change for consensus to move.
              </p>
              <p className="t-faint mt-4 text-xs uppercase tracking-[0.14em]">Weekly discussion format in development</p>
            </article>
          </div>
        </div>
      </section>

      <section aria-label="Listening desk" className="px-6 pb-4 md:px-12">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <SectionHeader index="C" title="Listening desk" blurb="Scripted, AI-narrated briefings with source notes." />
          </Reveal>
          <Reveal className="mt-8">
            <div id="podcast-desk">
              {episodesError ? <p role="alert" className="t-muted t-card border p-6">{episodesError}</p>
                : episodesLoading ? <p className="t-muted t-card border p-6">Loading published episodes…</p>
                  : <PodcastReadingRoom episodes={episodes} selectedEpisodeId={selectedEpisodeId} onEpisodeSelect={setSelectedEpisodeId} />}
            </div>
          </Reveal>
        </div>
      </section>

      <section aria-label="Podcast editorial review" className="px-6 pb-8 md:px-12">
        <div className="mx-auto max-w-6xl">
          <PodcastEditorialReview onPublished={handlePublishedEpisodes} />
        </div>
      </section>

      <section aria-label="Top stories audiobook" className="px-6 py-10 md:px-12">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <div className="coupon-edge p-2">
              <div className="t-card t-border border p-6 md:p-8">
                <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em]">
                  <Scissors className="h-4 w-4" aria-hidden="true" />
                  Clip and save: top 5 on the go
                </p>
                <p className="t-muted mt-2 max-w-2xl text-sm leading-relaxed">
                  Five crosschecks back to back for the commute. Playback controls live in the bar below once you press play.
                </p>
                <div className="mt-6">
                  <ListenAudiobook
                    stories={stories}
                    currentId={currentListenId}
                    playing={listeningPlaying}
                    onSelect={(id) => onListen && onListen(id)}
                    onPlayAll={() => stories[0] && onListen && onListen(stories[0].id)}
                  />
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      <section aria-label="Past episodes" className="px-6 pb-10 md:px-12">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <SectionHeader index="D" title="From the archive" blurb="Recent episodes. Sources listed in notes." />
          </Reveal>
          {episodes.length ? <div className="t-border mt-8 grid grid-cols-1 gap-0 border sm:grid-cols-2 lg:grid-cols-4">
            {episodes.slice(0, 4).map((ep, i) => (
              <article
                key={ep.id}
                className={`p-6 ${i > 0 ? 't-border border-t sm:border-l sm:border-t-0' : ''} ${
                  i === 2 ? 'max-lg:border-t max-lg:sm:border-l-0' : ''
                } ${i === 3 ? 'max-lg:border-t max-lg:sm:border-l' : ''}`}
              >
                <p className="kicker">
                  {ep.date} · {ep.topic}
                </p>
                <h3 className="headline-serif mt-2 text-lg leading-snug">
                    <button type="button" onClick={() => { setSelectedEpisodeId(ep.id); scrollToDesk() }} className="text-left">
                    {ep.title}
                  </button>
                </h3>
                <p className="t-faint mt-2 text-xs">
                  {Math.max(1, Math.ceil((ep.durationSeconds || 0) / 60))} min · AI-narrated
                </p>
              </article>
            ))}
          </div> : <p className="t-muted t-card mt-8 border p-6 text-center">{episodesLoading ? 'Loading episodes…' : 'New scripted briefings will appear here after editorial approval.'}</p>}
        </div>
      </section>

      <section aria-label="Follow" className="px-6 pb-14 md:px-12">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <FollowFolio onPlayLatest={scrollToDesk} />
          </Reveal>
        </div>
      </section>
    </div>
  )
}
