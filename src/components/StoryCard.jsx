import { Clock, Headphones, Share2 } from 'lucide-react'
import { listenMinsFor } from './ListenBar.jsx'

function TopicBadge({ topic }) {
  return <span className="text-[11px] font-semibold uppercase tracking-[0.18em] t-muted">{topic}</span>
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
        className="stagger-item t-card grid grid-cols-1 overflow-hidden rounded-2xl border text-left md:grid-cols-2"
      >
        <button type="button" onClick={open} aria-label={`Read: ${story.title}`} className="relative overflow-hidden text-left">
          <img src={story.image} alt="" className="h-56 w-full object-cover md:h-full" />
          <span aria-hidden="true" className="glass-nav absolute bottom-2 left-2 rounded-full px-2 py-0.5 text-[10px] t-faint">Illustrative image</span>
        </button>
        <div className="flex flex-col justify-center p-6 md:p-8">
          <div className="flex items-center justify-between gap-2">
            <TopicBadge topic={story.topic} />
            <span className="t-muted text-xs">{story.consensus}% consensus</span>
          </div>
          <button type="button" onClick={open} className="mt-3 text-left">
            <span className="font-display text-3xl font-extrabold leading-[1.02] tracking-tight md:text-5xl">
              {story.title}
            </span>
          </button>
          <p className="t-muted mt-3 font-display text-base font-medium leading-relaxed md:text-lg">{story.summary}</p>
          <div className="t-faint mt-5 flex flex-wrap items-center gap-4 text-xs">
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
              className="t-btn-primary flex items-center gap-1.5 rounded-full px-4 py-2 text-[13px] font-medium"
            >
              <Headphones className="h-3.5 w-3.5" />
              Listen
            </button>
            <button
              type="button"
              onClick={share}
              aria-label={`Share ${story.title}`}
              className="t-btn-outline flex items-center gap-1.5 rounded-full px-4 py-2 text-[13px]"
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
      className="stagger-item t-card flex flex-col overflow-hidden rounded-2xl border text-left"
    >
      <button type="button" onClick={open} aria-label={`Read: ${story.title}`} className="relative aspect-video overflow-hidden text-left">
        <img src={story.image} alt="" loading="lazy" className="h-full w-full object-cover" />
        <span aria-hidden="true" className="glass-nav absolute bottom-2 left-2 rounded-full px-2 py-0.5 text-[10px] t-faint">Illustrative image</span>
      </button>
      <div className="flex flex-1 flex-col p-5">
        <div className="flex items-center justify-between gap-2">
          <TopicBadge topic={story.topic} />
          <span className="t-muted text-xs">{story.consensus}% consensus</span>
        </div>
        <button type="button" onClick={open} className="mt-2.5 text-left">
          <span className="font-display text-2xl font-bold leading-[1.05] tracking-tight">{story.title}</span>
        </button>
        <p className="t-muted mt-2 line-clamp-2 font-display text-[15px] font-medium leading-relaxed">{story.summary}</p>
        <div className="t-faint mt-4 flex items-center gap-3 pt-1 text-xs">
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
        <div className="t-border mt-3.5 flex gap-2 border-t pt-3.5">
          <button
            type="button"
            onClick={listen}
            aria-label={`Listen to ${story.title}`}
            className="t-btn-outline flex flex-1 items-center justify-center gap-1.5 rounded-full px-3 py-1.5 text-xs"
          >
            <Headphones className="h-3.5 w-3.5" />
            Listen
          </button>
          <button
            type="button"
            onClick={share}
            aria-label={`Share ${story.title}`}
            className="t-btn-outline flex flex-1 items-center justify-center gap-1.5 rounded-full px-3 py-1.5 text-xs"
          >
            <Share2 className="h-3.5 w-3.5" />
            Share
          </button>
        </div>
      </div>
    </article>
  )
}
