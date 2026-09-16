import { SearchX } from 'lucide-react'
import StoryCard from './StoryCard.jsx'

export default function FeedGrid({ stories, resultLabel, onOpen, onListen, onShare, onClear }) {
  if (stories.length === 0) {
    return (
      <div className="page-enter flex flex-col items-center px-6 py-28 text-center md:px-12">
        <SearchX className="h-8 w-8 text-white/25" />
        <h2 className="mt-4 font-display text-3xl font-extrabold tracking-tight text-white">
          No stories match
        </h2>
        <p className="mt-2 text-sm text-white/50">
          {resultLabel}, try a different topic or search term.
        </p>
        <button
          type="button"
          onClick={onClear}
          className="mt-6 rounded-full border border-white/15 bg-white/5 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-white/10"
        >
          Clear filters
        </button>
      </div>
    )
  }

  const [featured, ...rest] = stories

  return (
    <div className="page-enter px-6 py-8 md:px-12 md:py-10">
      <p className="text-sm text-white/50">{resultLabel}</p>
      <div className="mt-5 grid grid-cols-1 gap-5 md:grid-cols-2 md:gap-6 lg:grid-cols-3">
        <div className="col-span-1 md:col-span-2 lg:col-span-3">
          <StoryCard story={featured} featured onOpen={onOpen} onListen={onListen} onShare={onShare} index={0} />
        </div>
        {rest.map((story, i) => (
          <StoryCard key={story.id} story={story} onOpen={onOpen} onListen={onListen} onShare={onShare} index={i + 1} />
        ))}
      </div>
    </div>
  )
}
