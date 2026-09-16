import { useEffect, useState } from 'react'
import {
  ArrowLeft,
  CheckCircle2,
  Clock,
  Headphones,
  Pause,
  Play,
  Share2,
  ShieldCheck,
  TriangleAlert,
} from 'lucide-react'
import { ACCENT } from '../theme.js'
import { listenMinsFor } from './ListenBar.jsx'
import ShareSheet from './ShareSheet.jsx'

const STANCE_DOT = {
  agree: ACCENT,
  context: 'rgba(255,255,255,0.4)',
  dispute: '#FF6B6B',
}

export default function Reader({ story, onBack, onListen, isListening, listeningPlaying }) {
  const [meter, setMeter] = useState(0)
  const [shareOpen, setShareOpen] = useState(false)

  useEffect(() => {
    const frame = requestAnimationFrame(() =>
      requestAnimationFrame(() => setMeter(story.consensus)),
    )
    return () => cancelAnimationFrame(frame)
  }, [story.consensus])

  return (
    <article className="page-enter perspective-stage mx-auto max-w-3xl px-6 py-8 md:px-12 md:py-10">
      <button
        type="button"
        onClick={onBack}
        className="flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-white/80 transition-colors hover:bg-white/10 hover:text-white"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to feed
      </button>

      <div className="mt-8 flex flex-wrap items-center gap-4 text-xs text-white/45">
        <span className="font-semibold uppercase tracking-[0.18em] text-white/55">
          {story.topic}
        </span>
        <span>{story.publishedAt}</span>
        <span className="flex items-center gap-1">
          <Clock className="h-3.5 w-3.5" />
          {story.readMins} min read
        </span>
        <span className="flex items-center gap-1">
          <Headphones className="h-3.5 w-3.5" />
          {listenMinsFor(story)} min listen
        </span>
      </div>

      <h1 className="mt-3 font-display text-5xl font-extrabold leading-[1.02] tracking-tight text-white md:text-6xl">
        <span className="display-3d">{story.title}</span>
      </h1>
      <p className="mt-4 font-display text-xl font-medium leading-relaxed text-white/80">
        {story.summary}
      </p>

      <div className="mt-6 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => onListen && onListen(story.id)}
          aria-label={isListening && listeningPlaying ? `Pause audiobook for ${story.title}` : `Listen to ${story.title}`}
          className="flex items-center gap-2 rounded-full bg-white px-5 py-2.5 text-sm font-medium text-black transition-colors hover:bg-white/85"
        >
          {isListening && listeningPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          {isListening && listeningPlaying ? 'Pause audio' : `Listen • ${listenMinsFor(story)} min`}
        </button>
        <button
          type="button"
          onClick={() => setShareOpen(true)}
          aria-label={`Share ${story.title}`}
          className="flex items-center gap-2 rounded-full border px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-white/10"
          style={{ borderColor: `${ACCENT}4D` }}
        >
          <Share2 className="h-4 w-4" />
          Share
        </button>
        <span className="self-center text-xs text-white/35">AI voice • mock audio • weaware.news/s/{story.id}</span>
      </div>

      <img
        src={story.image}
        alt=""
        className="mt-8 aspect-video w-full rounded-2xl border border-white/10 object-cover"
      />

      <div className="mt-8 space-y-5">
        {story.body.map((paragraph, i) => (
          <p key={i} className="leading-relaxed text-white/75">
            {paragraph}
          </p>
        ))}
      </div>

      <section className="mt-10 rounded-2xl border border-white/10 bg-white/[0.04] p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <ShieldCheck
              className="h-5 w-5"
              style={{ color: ACCENT }}
            />
            <h2 className="font-display text-xl font-extrabold tracking-tight text-white">
              Cross-checked by WeAware agents
            </h2>
          </div>
          <span className="rounded-full border border-white/15 bg-black/40 px-3 py-1 text-xs font-medium text-white/80">
            {story.sources.length} sources
          </span>
        </div>

        <div className="mt-5">
          <div className="flex items-center justify-between text-sm">
            <span className="text-white/60">Source consensus</span>
            <span className="font-semibold text-white">{story.consensus}%</span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full rounded-full transition-[width] duration-1000 ease-out"
              style={{
                width: `${meter}%`,
                background: `linear-gradient(to right, rgba(0,240,255,0.55), ${ACCENT})`,
              }}
            />
          </div>
        </div>

        <ul className="mt-5 space-y-3.5 border-t border-white/10 pt-5">
          {story.sources.map((source) => (
            <li key={source.outlet} className="flex items-start gap-3">
              <span
                className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
                style={{ backgroundColor: STANCE_DOT[source.stance] }}
              />
              <div>
                <p className="text-sm font-medium text-white">
                  {source.outlet}
                  <span className="ml-2 text-xs font-normal capitalize text-white/40">
                    {source.stance === 'agree'
                      ? 'corroborates'
                      : source.stance === 'context'
                        ? 'adds context'
                        : 'disputes'}
                  </span>
                </p>
                <p className="mt-0.5 text-sm leading-relaxed text-white/55">
                  {source.note}
                </p>
              </div>
            </li>
          ))}
        </ul>

        <div className="mt-5 border-t border-white/10 pt-5">
          {story.flaggedClaims.length === 0 ? (
            <p className="flex items-center gap-2 text-sm text-white/60">
              <CheckCircle2 className="h-4 w-4 text-white/50" />
              No low-confidence claims flagged in this story.
            </p>
          ) : (
            <ul className="space-y-3">
              {story.flaggedClaims.map((flag, i) => (
                <li
                  key={i}
                  className="rounded-xl border border-red-400/20 bg-red-400/5 p-4"
                >
                  <p className="flex items-start gap-2 text-sm font-medium text-white">
                    <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-red-300" />
                    {flag.claim}
                  </p>
                  <p className="mt-1.5 pl-6 text-sm leading-relaxed text-white/55">
                    {flag.reason}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
      <ShareSheet story={story} open={shareOpen} onClose={() => setShareOpen(false)} />
    </article>
  )
}
