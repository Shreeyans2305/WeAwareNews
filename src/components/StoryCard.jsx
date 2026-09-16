import { Clock, Headphones, Share2, Sparkles } from 'lucide-react'
import { listenMinsFor } from './ListenBar.jsx'

const ACCENT = '#00F0FF'

function TopicBadge({ topic }) {
  if (topic === 'Good News') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-amber-200/30 bg-amber-300/10 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-200">
        <Sparkles className="h-3 w-3" />
        Good News
      </span>
    )
  }
  return (
    <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-white/50">
      {topic}
    </span>
  )
}

export default function StoryCard({ story, featured = false, onOpen, onListen, onShare, index = 0 }) {
  const open = () => onOpen(story.id)
  const listen = (e) => {
    e.stopPropagation()
    if (onListen) onListen(story.id)
  }
  const share = (e) => {
    e.stopPropagation()
    if (onShare) onShare(story.id)
  }

  if (featured) {
    return (
      <article
        style={{ '--i': Math.min(index, 8) }}
        className={`stagger-item lift group grid grid-cols-1 overflow-hidden rounded-2xl border text-left md:grid-cols-2 ${
          story.topic === 'Good News'
            ? 'border-amber-200/25 bg-amber-100/[0.04]'
            : 'border-white/10 bg-white/[0.04] hover:border-white/25'
        }`}
      >
        <button type="button" onClick={open} aria-label={`Read: ${story.title}`} className="overflow-hidden text-left">
          <img
            src={story.image}
            alt=""
            className="h-56 w-full object-cover transition-transform duration-500 group-hover:scale-105 md:h-full"
          />
        </button>
        <div className="flex flex-col justify-center p-6 md:p-8">
          <div className="flex items-center justify-between gap-2">
            <TopicBadge topic={story.topic} />
            <span className="text-xs text-white/60">
              {story.consensus}% consensus
            </span>
          </div>
          <button type="button" onClick={open} className="mt-3 text-left">
            <span className="card-title-3d font-display text-3xl font-extrabold leading-[1.02] tracking-tight text-white md:text-5xl">
              {story.title}
            </span>
          </button>
          <p className="mt-3 font-display text-base font-medium leading-relaxed text-white/70 md:text-lg">{story.summary}</p>
          <div className="mt-5 flex flex-wrap items-center gap-4 text-xs text-white/40">
            <span>{story.sources.length} sources cross-checked</span>
            <span className="flex items-center gap-1">
              <Clock className="h-3.5 w-3.5" />
              {story.readMins} min read • {listenMinsFor(story)} min listen
            </span>
            <span>{story.publishedAt}</span>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={listen}
              aria-label={`Listen to ${story.title}`}
              className="flex items-center gap-1.5 rounded-full bg-white px-4 py-2 text-[13px] font-medium text-black hover:bg-white/85"
            >
              <Headphones className="h-3.5 w-3.5" />
              Listen
            </button>
            <button
              type="button"
              onClick={share}
              aria-label={`Share ${story.title}`}
              className="flex items-center gap-1.5 rounded-full border px-4 py-2 text-[13px] text-white hover:bg-white/10"
              style={{ borderColor: `${ACCENT}4D` }}
            >
              <Share2 className="h-3.5 w-3.5" />
              Share
            </button>
          </div>
        </div>
      </article>
    )
  }

  return (
    <article
      style={{ '--i': Math.min(index, 8) }}
      className={`stagger-item lift group flex flex-col overflow-hidden rounded-2xl border text-left ${
        story.topic === 'Good News'
          ? 'border-amber-200/25 bg-amber-100/[0.04]'
          : 'border-white/10 bg-white/[0.04] hover:border-white/25'
      }`}
    >
      <button type="button" onClick={open} aria-label={`Read: ${story.title}`} className="aspect-video overflow-hidden text-left">
        <img
          src={story.image}
          alt=""
          loading="lazy"
          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
        />
      </button>
      <div className="flex flex-1 flex-col p-5">
        <div className="flex items-center justify-between gap-2">
          <TopicBadge topic={story.topic} />
          <span className="text-xs text-white/60">
            {story.consensus}% consensus
          </span>
        </div>
        <button type="button" onClick={open} className="mt-2.5 text-left">
          <span className="card-title-3d font-display text-2xl font-bold leading-[1.05] tracking-tight text-white">
            {story.title}
          </span>
        </button>
        <p className="mt-2 line-clamp-2 font-display text-[15px] font-medium leading-relaxed text-white/70">
          {story.summary}
        </p>
        <div className="mt-4 flex items-center gap-3 pt-1 text-xs text-white/40">
          <span>{story.sources.length} sources</span>
          <span className="flex items-center gap-1">
            <Clock className="h-3.5 w-3.5" />
            {story.readMins} min
          </span>
          <span className="flex items-center gap-1">
            <Headphones className="h-3.5 w-3.5" />
            {listenMinsFor(story)} min
          </span>
          <span className="ml-auto">{story.publishedAt}</span>
        </div>
        <div className="mt-3.5 flex gap-2 border-t border-white/10 pt-3.5">
          <button
            type="button"
            onClick={listen}
            aria-label={`Listen to ${story.title}`}
            className="flex flex-1 items-center justify-center gap-1.5 rounded-full border border-white/15 px-3 py-1.5 text-xs text-white/80 hover:bg-white/10 hover:text-white"
          >
            <Headphones className="h-3.5 w-3.5" />
            Listen
          </button>
          <button
            type="button"
            onClick={share}
            aria-label={`Share ${story.title}`}
            className="flex flex-1 items-center justify-center gap-1.5 rounded-full border px-3 py-1.5 text-xs text-white/80 hover:bg-white/10 hover:text-white"
            style={{ borderColor: `${ACCENT}4D` }}
          >
            <Share2 className="h-3.5 w-3.5" />
            Share
          </button>
        </div>
      </div>
    </article>
  )
}
