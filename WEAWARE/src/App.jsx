import { lazy, Suspense, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { ArrowLeftRight, ArrowUpRight, Moon, Sun } from 'lucide-react'
import { fetchArticle, fetchArticles, fetchTopics, prioritizeStoriesWithImages, toStory } from './lib/api.js'
import { storyIdFromPath, storySharePath } from './lib/share.js'
import { ThemeProvider, useTheme } from './theme.js'
import Topbar from './components/Topbar.jsx'
import SiteFooter from './components/SiteFooter.jsx'
import ListenBar from './components/ListenBar.jsx'
import ShareSheet from './components/ShareSheet.jsx'
import AuthControl from './auth/AuthControl.jsx'
import { AuthProvider, useAuth } from './auth/AuthContext.jsx'

const NAV_LINKS = [
  { id: 'feed', label: 'Feed' },
  { id: 'newsletters', label: 'Newsletters' },
  { id: 'podcasts', label: 'Podcasts' },
  { id: 'sherlock', label: 'Sherlock · Experimental' },
  { id: 'about', label: 'About' },
]

const FeedGrid = lazy(() => import('./components/FeedGrid.jsx'))
const Reader = lazy(() => import('./components/Reader.jsx'))
const NewslettersPage = lazy(() => import('./components/NewslettersPage.jsx'))
const PodcastsPage = lazy(() => import('./components/PodcastsPage.jsx'))
const AboutPage = lazy(() => import('./components/AboutPage.jsx'))
const SherlockPage = lazy(() => import('./components/SherlockPage.jsx'))
const FEED_PAGE_SIZE = 24

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
  return (
    <>
      <section className="hero-home relative min-h-screen w-full overflow-hidden">
        <header className="hero-header">
          <button type="button" onClick={() => onNavigate('hero')} aria-label="WeAware home" className="hero-brand">
            <img src="/weaware-logo.png" alt="WeAware" />
          </button>
          <nav aria-label="Primary" className="hero-navigation">
            <div className="hero-nav-links">
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
            <div className="hero-nav-actions">
              <AuthControl />
              <ThemeToggle />
            </div>
          </nav>
        </header>

        <main className="hero-stage">
          <h1 className="hero-wordmark" aria-label="WeAware">
            <span aria-hidden="true">WE</span>
            <span aria-hidden="true">AWARE</span>
          </h1>
          <img className="hero-big-ben" src="/BigBen.png" alt="Elizabeth Tower, Big Ben" />
          <div className="hero-caption">
            <p>We bring multiple reports together, keeping sources and uncertainty in view so you can make up your own mind.</p>
            <button type="button" onClick={() => onNavigate('feed')} aria-label="Explore the news feed" className="hero-enter">
              <ArrowUpRight aria-hidden="true" />
            </button>
          </div>
        </main>
      </section>
      <PerspectiveSection />
    </>
  )
}

const PERSPECTIVES = [
  {
    id: 'one',
    point: 'Point 01',
    principle: 'Start with the source.',
    detail: 'Don’t let one source set the frame. See what other reporting adds, and where the accounts differ.',
    example: 'Investment & jobs',
    exampleDetail: 'One report leads with the public projects and hiring a proposed budget could support.',
    outlet: 'The Economic Times',
    outletMark: 'ET',
    reportTitle: '“Fiscally fit & on the jobs hunt”',
    reportSummary: 'The Economic Times puts the budget’s economic goals—keeping the deficit in check and encouraging employment—front and center.',
    reportImage: '/news/markets-1.jpg',
    reportImageAlt: 'Office towers viewed from below',
  },
  {
    id: 'two',
    point: 'Point 02',
    principle: 'Keep the trade-offs in view.',
    detail: 'Look beyond the headline. We show what’s supported, what differs, and what’s still unclear.',
    example: 'Cost & delivery',
    exampleDetail: 'Another focuses on borrowing, timing, and the conditions needed to deliver those plans.',
    outlet: 'The Indian Express',
    outletMark: 'IE',
    reportTitle: '“Election Outcome Budget”',
    reportSummary: 'The Indian Express reads the proposals in light of the election: the employment push as a response to job concerns, and support for Andhra Pradesh and Bihar as significant in a coalition government.',
    reportImage: '/news/world-1.jpg',
    reportImageAlt: 'A busy shipping port and its container cranes',
  },
]

function PerspectiveSection() {
  const [balance, setBalance] = useState(50)
  const [activeSource, setActiveSource] = useState(null)
  const visualRef = useRef(null)
  const previewRef = useRef(null)
  const pointerPositionRef = useRef(null)
  const pointerFrameRef = useRef(null)

  const showSource = (index) => setActiveSource((current) => current === index ? current : index)
  const positionPreviewAtPointer = (clientX, clientY) => {
    const bounds = visualRef.current?.getBoundingClientRect()
    const preview = previewRef.current
    if (!bounds || !preview) return
    preview.classList.add('is-following-cursor')

    const pointerX = clientX - bounds.left
    const pointerY = clientY - bounds.top
    const previewWidth = preview.offsetWidth
    const previewHeight = preview.offsetHeight
    const gap = 16
    let x = pointerX + gap
    let y = pointerY + gap

    if (x + previewWidth > bounds.width - 8) x = pointerX - previewWidth - gap
    if (y + previewHeight > bounds.height - 8) y = pointerY - previewHeight - gap

    preview.style.setProperty('--preview-x', `${Math.max(8, Math.min(x, bounds.width - previewWidth - 8))}px`)
    preview.style.setProperty('--preview-y', `${Math.max(8, Math.min(y, bounds.height - previewHeight - 8))}px`)
  }

  const showSourceAtPointer = (event) => {
    const bounds = visualRef.current?.getBoundingClientRect()
    if (!bounds || event.target.closest('.perspective-slider-wrap')) return
    pointerPositionRef.current = { x: event.clientX, y: event.clientY }
    if (pointerFrameRef.current === null) {
      pointerFrameRef.current = requestAnimationFrame(() => {
        pointerFrameRef.current = null
        if (pointerPositionRef.current) {
          positionPreviewAtPointer(pointerPositionRef.current.x, pointerPositionRef.current.y)
        }
      })
    }
    const splitX = bounds.left + bounds.width * (balance / 100)
    showSource(event.clientX < splitX ? 0 : 1)
  }

  useLayoutEffect(() => {
    if (activeSource !== null && pointerPositionRef.current) {
      positionPreviewAtPointer(pointerPositionRef.current.x, pointerPositionRef.current.y)
    }
  }, [activeSource])

  useEffect(() => () => {
    if (pointerFrameRef.current !== null) cancelAnimationFrame(pointerFrameRef.current)
  }, [])

  const handleSourceKeyDown = (event, index) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      showSource(index)
    }
  }

  return (
    <section className="perspective-section" aria-labelledby="perspective-title">
      <div className="perspective-inner">
        <div className="perspective-heading">
          <p className="perspective-eyebrow">A clearer view of the news</p>
          <h2 id="perspective-title">Hear both sides</h2>
        </div>

        <div
          className="perspective-layout"
          style={{ '--perspective-split': `${balance}%` }}
          onMouseLeave={() => {
            setActiveSource(null)
            pointerPositionRef.current = null
          }}
          onBlurCapture={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget)) setActiveSource(null)
          }}
        >
          <article
            className="perspective-copy perspective-copy-first"
            role="button"
            tabIndex={0}
            aria-label="Show The Economic Times report example"
            aria-haspopup="true"
            onMouseEnter={() => showSource(0)}
            onFocus={() => showSource(0)}
            onKeyDown={(event) => handleSourceKeyDown(event, 0)}
          >
            <p className="perspective-point">{PERSPECTIVES[0].point}</p>
            <h3>{PERSPECTIVES[0].principle}</h3>
            <p className="perspective-copy-detail">{PERSPECTIVES[0].detail}</p>
            <div className="perspective-rule" />
            <p className="perspective-example-label">Example</p>
            <h4>{PERSPECTIVES[0].example}</h4>
            <p className="perspective-copy-detail">{PERSPECTIVES[0].exampleDetail}</p>
          </article>

          <figure
            ref={visualRef}
            className={`perspective-visual ${activeSource !== null ? 'has-source-preview' : ''}`}
            onMouseMove={showSourceAtPointer}
            onClick={showSourceAtPointer}
          >
            <img src="/LeftRight.png" alt="A tall office building viewed from below" />
            <div className="perspective-tint perspective-tint-first" aria-hidden="true" />
            <div className="perspective-tint perspective-tint-second" aria-hidden="true" />
            <div className="perspective-divider" aria-hidden="true" />
            {activeSource !== null && (
              <aside
                ref={previewRef}
                className={`perspective-source-preview perspective-source-preview-${activeSource === 0 ? 'first' : 'second'}${pointerPositionRef.current ? ' is-following-cursor' : ''}`}
                role="status"
                aria-live="polite"
              >
                <img src={PERSPECTIVES[activeSource].reportImage} alt={PERSPECTIVES[activeSource].reportImageAlt} />
                <div className="perspective-source-preview-copy">
                  <p className="perspective-source-preview-outlet">
                    <span aria-hidden="true">{PERSPECTIVES[activeSource].outletMark}</span>
                    {PERSPECTIVES[activeSource].outlet}
                  </p>
                  <strong>{PERSPECTIVES[activeSource].reportTitle}</strong>
                  <p>{PERSPECTIVES[activeSource].reportSummary}</p>
                </div>
              </aside>
            )}
            <div className="perspective-slider-wrap">
              <ArrowLeftRight size={15} aria-hidden="true" />
              <label className="sr-only" htmlFor="perspective-balance">Compare the two perspectives</label>
              <input
                id="perspective-balance"
                type="range"
                min="8"
                max="92"
                value={balance}
                onChange={(event) => setBalance(Number(event.target.value))}
                aria-valuetext={`${balance}% perspective one, ${100 - balance}% perspective two`}
              />
              <span>Slide to compare</span>
            </div>
          </figure>

          <article
            className="perspective-copy perspective-copy-second"
            role="button"
            tabIndex={0}
            aria-label="Show The Indian Express report example"
            aria-haspopup="true"
            onMouseEnter={() => showSource(1)}
            onFocus={() => showSource(1)}
            onKeyDown={(event) => handleSourceKeyDown(event, 1)}
          >
            <p className="perspective-point">{PERSPECTIVES[1].point}</p>
            <h3>{PERSPECTIVES[1].principle}</h3>
            <p className="perspective-copy-detail">{PERSPECTIVES[1].detail}</p>
            <div className="perspective-rule" />
            <p className="perspective-example-label">Example</p>
            <h4>{PERSPECTIVES[1].example}</h4>
            <p className="perspective-copy-detail">{PERSPECTIVES[1].exampleDetail}</p>
          </article>
        </div>

        <p className="perspective-signoff">You decide<span>!!</span></p>
      </div>
    </section>
  )
}

function Shell() {
  const { theme } = useTheme()
  const { user } = useAuth()
  const initialStoryId = storyIdFromPath(window.location.pathname)
  const [view, setView] = useState(initialStoryId ? 'feed' : 'hero')
  const [topic, setTopic] = useState('All')
  const [query, setQuery] = useState('')
  const [activeId, setActiveId] = useState(initialStoryId)
  const [listenId, setListenId] = useState(null)
  const [listeningPlaying, setListeningPlaying] = useState(false)
  const [shareId, setShareId] = useState(null)
  const [stories, setStories] = useState([])
  const [topics, setTopics] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [apiError, setApiError] = useState('')
  const [detail, setDetail] = useState(null)
  const [articleError, setArticleError] = useState('')
  const filtered = stories

  useEffect(() => {
    const onPopState = () => {
      const id = storyIdFromPath(window.location.pathname)
      setActiveId(id)
      setView(id ? 'feed' : window.history.state?.view || 'hero')
      window.scrollTo(0, 0)
    }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    fetchTopics(controller.signal).then((result) => setTopics(result.topics || [])).catch(() => {})
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setLoading(true)
      fetchArticles({ topic, query, limit: FEED_PAGE_SIZE, signal: controller.signal })
        .then((result) => {
          setStories(prioritizeStoriesWithImages((result.articles || []).map(toStory)))
          setTotal(result.total || 0)
          setApiError('')
        })
        .catch((error) => {
          if (error.name !== 'AbortError') setApiError('We could not load the news feed. Check your connection and try again.')
        })
        .finally(() => setLoading(false))
    }, 200)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [topic, query, user])

  useEffect(() => {
    if (!activeId) {
      setDetail(null)
      setArticleError('')
      return
    }
    const controller = new AbortController()
    setDetail(null)
    setArticleError('')
    fetchArticle(activeId, controller.signal)
      .then((article) => setDetail(toStory(article)))
      .catch((error) => {
        if (error.name !== 'AbortError') {
          const cached = stories.find((story) => story.id === activeId)
          if (cached) setDetail(cached)
          else setArticleError('This story is unavailable. It may have been unpublished or the link may be incorrect.')
        }
      })
    return () => controller.abort()
  }, [activeId])

  const hasMoreStories = filtered.length < total
  const activeStory = detail || stories.find((story) => story.id === activeId) || null

  useEffect(() => {
    document.title = activeStory ? `${activeStory.title} — WeAware` : 'WeAware — Unbiased News, By Design'
  }, [activeStory])

  const navigate = (next) => {
    if (storyIdFromPath(window.location.pathname)) window.history.pushState({ view: next }, '', '/')
    else window.history.replaceState({ view: next }, '', '/')
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

  const resultLabel =
    `${total} ${total === 1 ? 'story' : 'stories'}` +
    (topic !== 'All' ? ` in ${topic}` : '') +
    (query.trim() !== '' ? ` matching “${query.trim()}”` : '')

  const openStory = (id) => {
    window.history.pushState({ view: 'feed' }, '', storySharePath(id))
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

  const loadMoreStories = async () => {
    setLoadingMore(true)
    try {
      const result = await fetchArticles({ topic, query, offset: stories.length })
      setStories((current) => prioritizeStoriesWithImages([...current, ...(result.articles || []).map(toStory)]))
      setTotal(result.total || 0)
    } catch {
      setApiError('We could not load more articles. Please try again.')
    } finally {
      setLoadingMore(false)
    }
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
        topics={topics}
        onTopic={setTopic}
        query={query}
        onQuery={setQuery}
        onHome={goHome}
      />
      <main key={`${view}-${activeId ?? 'list'}`}>
        <Suspense fallback={null}>
        {view === 'feed' && activeStory ? (
          <Reader
            key={activeStory.id}
            story={activeStory}
            onBack={() => {
              window.history.pushState({ view: 'feed' }, '', '/')
              setActiveId(null)
              window.scrollTo(0, 0)
            }}
            onListen={startListen}
            isListening={listenId === activeStory.id}
            listeningPlaying={listeningPlaying}
          />
        ) : null}
        {view === 'feed' && activeId && articleError ? (
          <section className="mx-auto max-w-4xl px-6 py-20 text-center"><h1 className="font-display text-3xl font-bold">Story unavailable</h1><p role="alert" className="t-muted mt-3">{articleError}</p><button type="button" onClick={() => navigate('feed')} className="t-btn-outline mt-6 rounded-full px-5 py-2.5">Browse the feed</button></section>
        ) : null}
        {view === 'feed' && activeId && !activeStory && !articleError ? (
          <section className="mx-auto max-w-4xl px-6 py-20 text-center t-muted" role="status">Loading this story…</section>
        ) : null}
        {view === 'feed' && !activeId && !activeStory ? (
          apiError ? <section className="mx-auto max-w-4xl px-6 py-20 text-center"><h1 className="font-display text-3xl font-bold">News feed unavailable</h1><p role="alert" className="t-muted mt-3">{apiError}</p></section>
            : loading && !stories.length ? <section className="mx-auto max-w-4xl px-6 py-20 text-center t-muted">Loading the latest cross-checked articles…</section>
              : <>
                <FeedGrid
                  stories={filtered}
                  lockedStories={[]}
                  resultLabel={resultLabel}
                  onOpen={openStory}
                  onListen={startListen}
                  onShare={setShareId}
                  onClear={() => { setTopic('All'); setQuery('') }}
                />
                {hasMoreStories && <div className="mx-auto max-w-4xl px-6 pb-12 text-center">
                  <button type="button" onClick={loadMoreStories} disabled={loadingMore} className="t-btn-outline rounded-full px-6 py-2.5 text-sm">{loadingMore ? 'Loading…' : 'Load more articles'}</button>
                </div>}
              </>
        ) : null}
        {view === 'newsletters' ? <NewslettersPage onOpenStory={openStory} stories={stories} topics={topics} /> : null}
        {view === 'podcasts' ? (
          <PodcastsPage onListen={startListen} currentListenId={listenId} listeningPlaying={listeningPlaying} stories={stories} />
        ) : null}
        {view === 'sherlock' ? <SherlockPage /> : null}
        {view === 'about' ? <AboutPage onNavigate={navigate} stories={stories} /> : null}
        </Suspense>
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
      <AuthProvider>
        <Shell />
      </AuthProvider>
    </ThemeProvider>
  )
}
