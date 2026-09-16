import { Search } from 'lucide-react'
import { ACCENT } from '../theme.js'
import { TOPICS } from '../data/stories.js'

const PAGES = [
  { id: 'feed', label: 'Feed' },
  { id: 'newsletters', label: 'Newsletters' },
  { id: 'podcasts', label: 'Podcasts' },
  { id: 'about', label: 'About' },
]

export default function Topbar({
  page,
  onNavigate,
  activeTopic,
  onTopic,
  query,
  onQuery,
  onHome,
}) {
  const isFeed = page === 'feed'

  return (
    <header className="sticky top-0 z-30 border-b border-white/10 bg-black/80 backdrop-blur-xl">
      <div className="flex flex-wrap items-center gap-3 px-6 py-3 md:px-12 md:py-4">
        <button type="button" onClick={onHome} aria-label="Back to WeAware home" className="shrink-0">
          <img src="/weaware-logo.png" alt="WeAware" className="h-9 w-auto" />
        </button>

        <nav aria-label="Primary" className="perspective-stage flex flex-wrap items-center gap-1">
          {PAGES.map((link) => {
            const active = page === link.id
            return (
              <button
                key={link.id}
                type="button"
                onClick={() => onNavigate(link.id)}
                aria-current={active ? 'page' : undefined}
                className={`nav-3d rounded-full px-4 py-1.5 text-[15px] transition-colors md:px-5 ${
                  active
                    ? 'bg-white text-black'
                    : 'text-white/60 hover:bg-white/10 hover:text-white'
                }`}
              >
                {link.label}
              </button>
            )
          })}
        </nav>

        <div className="ml-auto flex items-center gap-4">
          {isFeed && (
            <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 transition-colors focus-within:border-white/30">
              <Search className="h-4 w-4 shrink-0 text-white/40" />
              <input
                value={query}
                onChange={(e) => onQuery(e.target.value)}
                placeholder="Search stories…"
                aria-label="Search stories"
                className="w-36 bg-transparent text-sm text-white outline-none placeholder-white/35 md:w-56"
              />
            </div>
          )}
          <div className="hidden items-center gap-2 sm:flex">
            <span className="signal-dot h-1.5 w-1.5 rounded-full" style={{ backgroundColor: ACCENT }} />
            <span className="text-xs text-white/60">Agents active</span>
          </div>
        </div>
      </div>

      {isFeed && (
        <div className="flex items-center gap-1 overflow-x-auto px-6 pb-3 md:px-12">
          {['All', ...TOPICS].map((topic) => {
            const active = activeTopic === topic
            return (
              <button
                key={topic}
                type="button"
                onClick={() => onTopic(topic)}
                aria-pressed={active}
                className={`nav-3d shrink-0 rounded-full px-5 py-1.5 text-[15px] transition-colors ${
                  active ? 'bg-white text-black' : 'text-white/60 hover:bg-white/10 hover:text-white'
                }`}
              >
                {topic}
              </button>
            )
          })}
        </div>
      )}
    </header>
  )
}
