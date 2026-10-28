import { LockKeyhole } from 'lucide-react'
import StoryArtwork from './StoryArtwork.jsx'

export default function LockedStoryGrid({
  stories = [],
  onUnlock,
  eyebrow = 'More coverage',
  heading = 'Stories waiting to be explored',
  description = 'Sign in to read these stories',
  className = 'px-6 pb-10 md:px-12',
}) {
  if (!stories.length) return null

  return (
    <section aria-labelledby="locked-stories-title" className={className}>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow-kanit t-muted text-[11px]">{eyebrow}</p>
          <h2 id="locked-stories-title" className="mt-1 font-display text-2xl font-bold tracking-tight">{heading}</h2>
        </div>
        <p className="t-faint text-sm">{description}</p>
      </div>
      <div className="grid grid-cols-1 gap-5 md:grid-cols-2 md:gap-6 lg:grid-cols-3">
        {stories.map((story) => (
          <div key={story.id} className="relative overflow-hidden rounded-2xl">
            <article aria-hidden="true" className="t-card pointer-events-none select-none overflow-hidden rounded-2xl border blur-[5px] opacity-60">
              <div className="aspect-video overflow-hidden">
                {story.image
                  ? <img src={story.image} alt="" className="h-full w-full object-cover" />
                  : <StoryArtwork story={story} />}
              </div>
              <div className="p-5">
                <span className="t-muted text-[11px] font-semibold uppercase tracking-[0.18em]">{story.topic}</span>
                <h3 className="mt-2 font-display text-2xl font-bold leading-tight">{story.title}</h3>
                <p className="t-muted mt-2 line-clamp-3 font-display text-[15px] leading-relaxed">{story.summary}</p>
              </div>
            </article>
            <button
              type="button"
              onClick={onUnlock}
              aria-label="Sign in to reveal a locked story"
              style={{ backgroundColor: 'color-mix(in srgb, var(--bg) 30%, transparent)' }}
              className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-4 text-center transition-opacity hover:opacity-90"
            >
              <span className="glass-nav inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium">
                <LockKeyhole className="h-4 w-4" /> Sign in to reveal
              </span>
            </button>
          </div>
        ))}
      </div>
    </section>
  )
}
