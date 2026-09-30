import { useState } from 'react'
import { Moon, Sun } from 'lucide-react'
import { stories } from './data/stories.js'
import { ThemeProvider, useTheme } from './theme.js'
import Topbar from './components/Topbar.jsx'
import FeedGrid from './components/FeedGrid.jsx'
import Reader from './components/Reader.jsx'
import NewslettersPage from './components/NewslettersPage.jsx'
import PodcastsPage from './components/PodcastsPage.jsx'
import AboutPage from './components/AboutPage.jsx'
import SiteFooter from './components/SiteFooter.jsx'
import ListenBar from './components/ListenBar.jsx'
import ShareSheet from './components/ShareSheet.jsx'

const NAV_LINKS = [
  { id: 'feed', label: 'Feed' },
  { id: 'newsletters', label: 'Newsletters' },
  { id: 'podcasts', label: 'Podcasts' },
  { id: 'about', label: 'About' },
]

function ThemeToggle() {
  const { theme, toggle } = useTheme()
  const dark = theme === 'dark'
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
      aria-pressed={dark}
      className="icon-btn"
    >
      {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  )
}

function Hero({ onNavigate }) {
  const [joined, setJoined] = useState(false)

  return (
    <section className="t-bg relative min-h-screen w-full overflow-hidden">
      <video
        className="hero-media absolute inset-0 h-full w-full object-cover opacity-40"
        autoPlay
        loop
        muted
        playsInline
        preload="auto"
        poster="/weaware-poster.jpg"
        src="/weaware-bg.mp4"
      />

      <div className="relative z-10 flex min-h-screen flex-col px-4 pt-3 md:px-8">
        <nav aria-label="Primary" className="glass-nav mx-auto flex w-full max-w-4xl items-center gap-4 rounded-2xl px-4 py-2.5">
          <button type="button" onClick={() => onNavigate('hero')} aria-label="WeAware home" className="flex shrink-0 items-center gap-2">
            <img src="/weaware-logo.png" alt="WeAware — globe with WEAWARE banner" className="h-6 w-auto" />
            <span className="font-display text-[15px] font-bold tracking-tight">WeAware</span>
          </button>

          <div className="hidden items-center gap-5 md:flex">
            {NAV_LINKS.map((link) => (
              <button
                key={link.id}
                type="button"
                onClick={() => onNavigate(link.id)}
                className="nav-link"
              >
                {link.label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-4 md:hidden">
            {NAV_LINKS.slice(0, 3).map((link) => (
              <button
                key={link.id}
                type="button"
                onClick={() => onNavigate(link.id)}
                className="nav-link"
              >
                {link.label}
              </button>
            ))}
          </div>

          <div className="ml-auto flex items-center gap-2">
            <a href="#waitlist" className="t-btn-primary rounded-full px-4 py-1.5 text-[13px] font-medium">
              Join waitlist
            </a>
            <ThemeToggle />
          </div>
        </nav>

        <main className="mt-auto flex flex-col justify-end gap-8 px-6 pb-14 md:px-12 md:pb-16">
          <div className="max-w-3xl">
            <div className="hero-rise glass-nav mb-5 inline-flex items-center gap-2 rounded-full px-3.5 py-1.5" style={{ '--i': 0 }}>
              <span className="signal-dot h-1.5 w-1.5 rounded-full" />
              <span className="eyebrow-kanit text-[12px]">Cross-checked news, with sources shown</span>
            </div>
            <h1 className="hero-rise font-display text-6xl font-extrabold leading-[0.98] tracking-tight md:text-7xl lg:text-[5.4rem]" style={{ '--i': 1 }}>
              News, cross-checked by AI agents, not ranked for outrage.
            </h1>
            <p className="hero-rise t-muted mt-4 font-display text-lg font-medium md:text-xl" style={{ '--i': 2 }}>
              WeAware cross-references every source, flags disagreement instead of hiding it, and always links back
              to the original reporting.
            </p>
            {joined ? (
              <p id="waitlist" role="status" className="hero-rise glass-nav mt-8 inline-flex items-center gap-2 rounded-full px-5 py-3 text-sm" style={{ '--i': 3 }}>
                <span className="signal-dot h-1.5 w-1.5 rounded-full" />
                You are on the waitlist. Watch your inbox for early access.
              </p>
            ) : (
              <form
                id="waitlist"
                onSubmit={(e) => {
                  e.preventDefault()
                  setJoined(true)
                }}
                className="hero-rise glass-nav mt-8 inline-flex max-w-full flex-col gap-2 rounded-2xl p-1.5 sm:flex-row sm:items-center sm:rounded-full"
                style={{ '--i': 3 }}
              >
                <label htmlFor="hero-email" className="sr-only">Email address</label>
                <input
                  id="hero-email"
                  type="email"
                  required
                  placeholder="Get early access"
                  aria-label="Email address"
                  className="t-field w-full rounded-xl bg-transparent px-4 py-2 text-sm outline-none sm:w-64 sm:rounded-full"
                />
                <button type="submit" className="t-btn-primary rounded-xl px-6 py-2.5 text-sm font-medium sm:rounded-full">
                  Join waitlist
                </button>
              </form>
            )}
          </div>
        </main>
      </div>
    </section>
  )
}

function Shell() {
  const { theme } = useTheme()
  const [view, setView] = useState('hero')
  const [topic, setTopic] = useState('All')
  const [query, setQuery] = useState('')
  const [activeId, setActiveId] = useState(null)
  const [listenId, setListenId] = useState(null)
  const [listeningPlaying, setListeningPlaying] = useState(false)
  const [shareId, setShareId] = useState(null)

  const navigate = (next) => {
    if (next === 'hero') {
      setActiveId(null)
      setView('hero')
    } else {
      setActiveId(null)
      setView(next)
    }
    window.scrollTo(0, 0)
  }

  if (view === 'hero') {
    return (
      <div data-theme={theme} className="t-bg min-h-screen">
        <Hero onNavigate={navigate} />
      </div>
    )
  }

  const q = query.trim().toLowerCase()
  const filtered = stories.filter(
    (story) =>
      (topic === 'All' || story.topic === topic) &&
      (q === '' || `${story.title} ${story.summary}`.toLowerCase().includes(q)),
  )
  const activeStory = stories.find((story) => story.id === activeId) ?? null

  const resultLabel =
    `${filtered.length} ${filtered.length === 1 ? 'story' : 'stories'}` +
    (topic !== 'All' ? ` in ${topic}` : '') +
    (query.trim() !== '' ? ` matching “${query.trim()}”` : '')

  const openStory = (id) => {
    setActiveId(id)
    setView('feed')
    window.scrollTo(0, 0)
  }

  const startListen = (id) => {
    if (listenId === id) {
      setListeningPlaying((p) => !p)
    } else {
      setListenId(id)
      setListeningPlaying(true)
    }
  }

  const stepListen = (dir) => {
    const ids = filtered.length > 0 ? filtered.map((s) => s.id) : stories.map((s) => s.id)
    const idx = ids.indexOf(listenId)
    if (idx === -1) {
      startListen(ids[0])
      return
    }
    const nextIdx = (idx + dir + ids.length) % ids.length
    setListenId(ids[nextIdx])
    setListeningPlaying(true)
  }

  const goHome = () => navigate('hero')
  const listenStory = stories.find((s) => s.id === listenId) ?? null
  const shareStory = stories.find((s) => s.id === shareId) ?? null

  return (
    <div data-theme={theme} className={`t-bg min-h-screen ${listenStory ? 'pb-32' : ''}`}>
      <Topbar
        page={view}
        onNavigate={navigate}
        activeTopic={topic}
        onTopic={setTopic}
        query={query}
        onQuery={setQuery}
        onHome={goHome}
      />
      <main key={`${view}-${activeId ?? 'list'}`}>
        {view === 'feed' && activeStory ? (
          <Reader
            key={activeStory.id}
            story={activeStory}
            onBack={() => {
              setActiveId(null)
              window.scrollTo(0, 0)
            }}
            onListen={startListen}
            isListening={listenId === activeStory.id}
            listeningPlaying={listeningPlaying}
          />
        ) : null}
        {view === 'feed' && !activeStory ? (
          <FeedGrid
            stories={filtered}
            resultLabel={resultLabel}
            onOpen={openStory}
            onListen={startListen}
            onShare={setShareId}
            onClear={() => {
              setTopic('All')
              setQuery('')
            }}
          />
        ) : null}
        {view === 'newsletters' ? <NewslettersPage onOpenStory={openStory} /> : null}
        {view === 'podcasts' ? (
          <PodcastsPage onListen={startListen} currentListenId={listenId} listeningPlaying={listeningPlaying} />
        ) : null}
        {view === 'about' ? <AboutPage onNavigate={navigate} /> : null}
      </main>
      <SiteFooter onNavigate={navigate} current={view} />
      {listenStory ? (
        <ListenBar
          story={listenStory}
          queue={filtered.length > 0 ? filtered : stories}
          playing={listeningPlaying}
          onToggle={() => setListeningPlaying((p) => !p)}
          onClose={() => {
            setListenId(null)
            setListeningPlaying(false)
          }}
          onSelect={startListen}
          onNext={() => stepListen(1)}
          onPrev={() => stepListen(-1)}
        />
      ) : null}
      <ShareSheet story={shareStory} open={!!shareStory} onClose={() => setShareId(null)} />
    </div>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <Shell />
    </ThemeProvider>
  )
}
