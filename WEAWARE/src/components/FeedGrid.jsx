import { SearchX } from 'lucide-react'
import StoryCard from './StoryCard.jsx'
import LockedStoryGrid from './LockedStoryGrid.jsx'
import InteractiveSelector from './ui/interactive-selector.jsx'

export default function FeedGrid({ stories, lockedStories = [], resultLabel, onOpen, onUnlock, onListen, onShare, onClear }) {
  if (stories.length === 0) {
    return (
      <div className="page-enter flex flex-col items-center px-6 py-28 text-center md:px-12">
        <SearchX className="t-faint h-8 w-8" />
        <h2 className="mt-4 font-display text-3xl font-extrabold tracking-tight">No stories match</h2>
        <p className="t-muted mt-2 text-sm">{resultLabel}, try a different topic or search term.</p>
        <button type="button" onClick={onClear} className="t-btn-outline mt-6 rounded-full px-5 py-2 text-sm font-medium">
          Clear filters
        </button>
      </div>
    )
  }

  const [featured, ...rest] = stories

  return (
    <div className="page-enter">
      {/* Expanding selector hero — top of Feed. Click to expand, click active to read. */}
      <InteractiveSelector stories={stories} onOpen={onOpen} />
      <div className="px-6 py-8 md:px-12 md:py-10">
        <p className="t-muted text-sm">{resultLabel}</p>
        <div className="mt-5 grid grid-cols-1 gap-5 md:grid-cols-2 md:gap-6 lg:grid-cols-3">
          <div className="col-span-1 md:col-span-2 lg:col-span-3">
            <StoryCard story={featured} featured onOpen={onOpen} onListen={onListen} onShare={onShare} index={0} />
          </div>
          {rest.map((story, i) => (
            <StoryCard key={story.id} story={story} onOpen={onOpen} onListen={onListen} onShare={onShare} index={i + 1} />
          ))}
        </div>
      </div>
      <LockedStoryGrid stories={lockedStories} onUnlock={onUnlock} />
    </div>
  )
}
