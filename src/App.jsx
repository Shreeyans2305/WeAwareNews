import { useState } from 'react'
import { stories } from './data/stories.js'
import Topbar from './components/Topbar.jsx'
import FeedGrid from './components/FeedGrid.jsx'
import Reader from './components/Reader.jsx'
import NewslettersPage from './components/NewslettersPage.jsx'
import PodcastsPage from './components/PodcastsPage.jsx'
import AboutPage from './components/AboutPage.jsx'
import SiteFooter from './components/SiteFooter.jsx'
import ListenBar from './components/ListenBar.jsx'
import ShareSheet from './components/ShareSheet.jsx'

const ACCENT = '#00F0FF'
const CTA_GRADIENT = 'linear-gradient(to bottom, #2B2B2B, #101010)'
const CTA_GLOW = '0 0 24px rgba(0, 240, 255, 0.18)'
const NAV_LINKS = [
  { id: 'feed', label: 'Feed' },
  { id: 'newsletters', label: 'Newsletters' },
  { id: 'podcasts', label: 'Podcasts' },
  { id: 'about', label: 'About' },
]

function Hero({ onNavigate }) {
  const [joined, setJoined] = useState(false)

  return (
    <section className="relative min-h-screen w-full overflow-hidden bg-black">
      <video
        className="hero-media absolute inset-0 h-full w-full object-cover"
        autoPlay
        loop
        muted
        playsInline
        preload="auto"
        poster="/weaware-poster.jpg"
        src="/weaware-bg.mp4"
      />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-44 bg-gradient-to-b from-black/60 via-black/20 to-transparent" />
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-[78%] bg-gradient-to-t from-black/80 via-black/35 to-transparent" />

      <div className="relative z-10 flex min-h-screen flex-col">
        <nav aria-label="Primary" className="flex flex-wrap items-center justify-between gap-3 px-6 py-5 md:px-12 md:py-6">
          <button type="button" onClick={() => onNavigate('hero')} aria-label="WeAware home">
            <img
              src="/weaware-logo.png"
              alt="WeAware — globe with WEAWARE banner"
              className="h-10 w-auto drop-shadow-[0_2px_12px_rgba(0,0,0,0.55)] md:h-12"
            />
          </button>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex flex-wrap items-center gap-1 rounded-full border border-white/15 bg-black/35 px-1.5 py-1.5 shadow-lg backdrop-blur-xl">
              {NAV_LINKS.map((link) => (
                <button
                  key={link.id}
                  type="button"
                  onClick={() => onNavigate(link.id)}
                  className="nav-3d rounded-full px-5 py-1.5 text-[15px] text-white/85 transition-colors hover:bg-white/15 hover:text-white hover:underline hover:underline-offset-4"
                  style={{ textDecorationColor: ACCENT }}
                >
                  {link.label}
                </button>
              ))}
            </div>
            <a
              href="#waitlist"
              className="nav-3d flex items-center self-stretch rounded-full border px-5 py-2 text-[15px] text-white transition-opacity hover:opacity-90"
              style={{
                background: CTA_GRADIENT,
                borderColor: `${ACCENT}4D`,
                boxShadow: CTA_GLOW,
              }}
            >
              Join waitlist
            </a>
          </div>
        </nav>

        <main className="perspective-stage mt-auto flex flex-col justify-end gap-8 px-6 pb-14 md:px-12 md:pb-16">
          <div className="max-w-3xl">
            <div className="hero-rise mb-5 inline-flex items-center gap-2 rounded-full border border-white/15 bg-black/35 px-3.5 py-1.5 backdrop-blur-xl" style={{ '--i': 0 }}>
              <span className="signal-dot h-1.5 w-1.5 rounded-full" style={{ backgroundColor: ACCENT }} />
              <span className="eyebrow-kanit text-[12px] text-white/80">
                Cross-checked news, with sources shown
              </span>
            </div>
            <h1
              className="hero-rise font-display text-6xl font-extrabold leading-[0.98] tracking-tight text-white md:text-7xl lg:text-[5.4rem]"
              style={{ '--i': 1, textShadow: '0 2px 24px rgba(0,0,0,0.5)' }}
            >
              <span className="display-3d display-3d-gradient">
                News, cross-checked by AI agents, not ranked for outrage.
              </span>
            </h1>
            <p
              className="hero-rise mt-4 font-display text-lg font-medium text-white/80 md:text-xl"
              style={{ '--i': 2, textShadow: '0 1px 12px rgba(0,0,0,0.5)' }}
            >
              WeAware cross-references every source, flags disagreement instead
              of hiding it, and always links back to the original reporting.
            </p>
            {joined ? (
              <p
                id="waitlist"
                role="status"
                className="hero-rise mt-8 inline-flex items-center gap-2 rounded-full border border-white/15 bg-black/45 px-5 py-3 text-sm text-white backdrop-blur-xl"
                style={{ '--i': 3 }}
              >
                <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: ACCENT }} />
                You are on the waitlist. Watch your inbox for early access.
              </p>
            ) : (
            <form
              id="waitlist"
              onSubmit={(e) => {
                e.preventDefault()
                setJoined(true)
              }}
              className="hero-rise mt-8 inline-flex max-w-full flex-col gap-2 rounded-2xl bg-white p-1.5 shadow-2xl sm:flex-row sm:items-center sm:rounded-full"
              style={{ '--i': 3 }}
            >
              <label htmlFor="hero-email" className="sr-only">
                Email address
              </label>
              <input
                id="hero-email"
                type="email"
                required
                placeholder="Get early access"
                aria-label="Email address"
                className="w-full rounded-xl bg-transparent px-4 py-2 text-sm text-gray-900 outline-none placeholder-gray-400 sm:w-64 sm:rounded-full"
              />
              <button
                type="submit"
                className="rounded-xl border px-6 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90 sm:rounded-full"
                style={{
                  background: CTA_GRADIENT,
                  borderColor: `${ACCENT}4D`,
                  boxShadow: CTA_GLOW,
                }}
              >
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

export default function App() {
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
    return <Hero onNavigate={navigate} />
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
    <div className={`min-h-screen bg-black text-white ${listenStory ? 'pb-32' : ''}`}>
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
