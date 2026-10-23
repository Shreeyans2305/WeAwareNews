import { Moon, Search, Sun } from 'lucide-react'
import { TOPICS } from '../data/stories.js'
import { useTheme } from '../theme.js'
import AuthControl from '../auth/AuthControl.jsx'

const PAGES = [
  { id: 'feed', label: 'Feed' },
  { id: 'newsletters', label: 'Newsletters' },
  { id: 'podcasts', label: 'Podcasts' },
  { id: 'about', label: 'About' },
]

export default function Topbar({ page, onNavigate, activeTopic, onTopic, query, onQuery, onHome, topics = [] }) {
  const { theme, toggle } = useTheme()
  const dark = theme === 'dark'
  const isFeed = page === 'feed'

  return (
    <div className="t-bg sticky top-0 z-30 px-4 pt-3 md:px-8">
      <header className="glass-nav mx-auto flex max-w-4xl flex-wrap items-center gap-x-2 gap-y-1 rounded-2xl px-3 py-2.5 md:flex-nowrap md:gap-4 md:px-4">
        <button type="button" onClick={onHome} aria-label="Back to WeAware home" className="flex shrink-0 items-center gap-2">
          <img src="/weaware-logo.png" alt="WeAware" className="h-6 w-auto" />
          <span className="font-display text-[15px] font-bold tracking-tight">WeAware</span>
        </button>

        <nav aria-label="Primary" className="hidden items-center gap-5 md:flex">
          {PAGES.map((link) => (
            <button
              key={link.id}
              type="button"
              onClick={() => onNavigate(link.id)}
              aria-current={page === link.id ? 'page' : undefined}
              data-active={page === link.id}
              className="nav-link"
            >
              {link.label}
            </button>
          ))}
        </nav>

        <div className="order-2 ml-auto flex shrink-0 items-center gap-1 md:order-none">
          {isFeed && (
            <div className="flex items-center gap-2">
              <Search className="t-faint h-4 w-4 shrink-0" />
              <input
                value={query}
                onChange={(e) => onQuery(e.target.value)}
                placeholder="Search"
                aria-label="Search stories"
                className="t-field w-12 bg-transparent text-sm outline-none placeholder:text-[var(--faint)] focus:w-20 md:w-28 md:focus:w-32 lg:focus:w-44"
                style={{ transition: 'width 200ms ease' }}
              />
            </div>
          )}
          <AuthControl />
          <button
            type="button"
            onClick={toggle}
            aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
            className="icon-btn"
          >
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
        </div>

        <nav aria-label="Primary mobile" className="order-3 flex w-full items-center justify-between gap-1 md:hidden">
          {PAGES.map((link) => (
            <button
              key={link.id}
              type="button"
              onClick={() => onNavigate(link.id)}
              aria-current={page === link.id ? 'page' : undefined}
              data-active={page === link.id}
              className="nav-link"
            >
              {link.label}
            </button>
          ))}
        </nav>
      </header>

      {isFeed && (
        <div className="mx-auto flex max-w-4xl items-center gap-5 overflow-x-auto px-4 pb-2 pt-2.5">
          {['All', ...(topics.length ? topics : TOPICS)].map((topic) => (
            <button
              key={topic}
              type="button"
              onClick={() => onTopic(topic)}
              aria-pressed={activeTopic === topic}
              data-active={activeTopic === topic}
              className="topic-link"
            >
              {topic}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
