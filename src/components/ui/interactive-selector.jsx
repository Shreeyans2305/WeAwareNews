import { useEffect, useState } from 'react'
import { ArrowRight, Cpu, Leaf, LineChart, Globe2, Sparkles } from 'lucide-react'

/**
 * InteractiveSelector — Vite/JSX port of the 21st.dev `interactive-selector`.
 *
 * Adaptations from the pasted TSX:
 * - `react-icons/fa` -> `lucide-react` (already in this repo, consistent icons)
 * - `https://cdn.21st.dev/...` mirror images -> Unsplash stock (mirrors 404)
 *   + accepts real story images via `items` prop (local `/news/*.jpg`)
 * - `<style jsx>` (Next.js only) -> plain `<style>` (Vite has no `jsx` prop)
 * - Hard `bg-[#222]` / white text -> theme-aware (`t-bg`, `var(--*)`) so it
 *   follows WeAware light/dark mode
 * - Fixed `min-w-[600px]` row -> responsive: vertical stack on mobile,
 *   expanding row on md+ (original broke <600px viewports)
 * - Now props-driven: `items` + `onOpen`, so the Feed can pass live stories.
 *   Click once to expand, click active card / "Read story" to open.
 */

const FALLBACK_ITEMS = [
  {
    id: 'ai',
    topic: 'AI',
    title: 'AI, cross-checked',
    description: 'Frontier evals, agent trials, chip rules — sources shown.',
    image:
      'https://images.unsplash.com/photo-1677442136019-21780ecad995?q=80&w=1200&auto=format&fit=crop',
    Icon: Cpu,
  },
  {
    id: 'climate',
    topic: 'Climate',
    title: 'Climate signals',
    description: 'Reefs, storage, fuels — what agrees, what disputes.',
    image:
      'https://images.unsplash.com/photo-1469474968028-56623f02e42e?q=80&w=1200&auto=format&fit=crop',
    Icon: Leaf,
  },
  {
    id: 'markets',
    topic: 'Markets',
    title: 'Markets, decoded',
    description: 'Rates, rare earths, IPOs — hype flagged inline.',
    image:
      'https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?q=80&w=1200&auto=format&fit=crop',
    Icon: LineChart,
  },
  {
    id: 'world',
    topic: 'World',
    title: 'World in brief',
    description: 'Treaties, relief corridors, observer missions.',
    image:
      'https://images.unsplash.com/photo-1451187580459-43490279c429?q=80&w=1200&auto=format&fit=crop',
    Icon: Globe2,
  },
  {
    id: 'good-news',
    topic: 'Good News',
    title: 'Good News',
    description: 'Repairs, school streets, recoveries worth sharing.',
    image:
      'https://images.unsplash.com/photo-1441974231531-c6227db76b6e?q=80&w=1200&auto=format&fit=crop',
    Icon: Sparkles,
  },
]

const TOPIC_ICONS = {
  AI: Cpu,
  Climate: Leaf,
  Markets: LineChart,
  World: Globe2,
  'Good News': Sparkles,
}

function toSelectorItems(stories) {
  if (!stories || stories.length === 0) return FALLBACK_ITEMS
  return stories.slice(0, 5).map((s) => ({
    id: s.id,
    topic: s.topic,
    title: s.title,
    description: s.summary,
    image: s.image,
    consensus: s.consensus,
    Icon: TOPIC_ICONS[s.topic] ?? Sparkles,
  }))
}

export default function InteractiveSelector({
  stories,
  items,
  onOpen,
  eyebrow = 'Top stories',
  heading = 'Stories in focus',
}) {
  const resolved = items ?? toSelectorItems(stories)
  const [activeIndex, setActiveIndex] = useState(0)
  const [animatedOptions, setAnimatedOptions] = useState([])

  useEffect(() => {
    setAnimatedOptions([])
    setActiveIndex(0)
    const timers = resolved.map((_, i) =>
      setTimeout(() => {
        setAnimatedOptions((prev) => (prev.includes(i) ? prev : [...prev, i]))
      }, 180 * i),
    )
    return () => timers.forEach((t) => clearTimeout(t))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resolved.length])

  const handleOptionClick = (index) => {
    if (index !== activeIndex) {
      setActiveIndex(index)
      return
    }
    // Clicking the already-active panel opens the story (if wired).
    const item = resolved[index]
    if (item?.id && onOpen) onOpen(item.id)
  }

  const handleKeyDown = (e, index) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      handleOptionClick(index)
    }
    if (e.key === 'ArrowRight') setActiveIndex((a) => Math.min(a + 1, resolved.length - 1))
    if (e.key === 'ArrowLeft') setActiveIndex((a) => Math.max(a - 1, 0))
  }

  return (
    <section aria-label="Featured stories selector" className="t-bg w-full">
      <div className="mx-auto w-full max-w-4xl px-6 pt-8 text-center md:px-12">
        <p className="animate-fadeInTop delay-300 eyebrow-kanit t-muted text-[12px]">
          {eyebrow}
        </p>
        <h2 className="animate-fadeInTop delay-300 font-display mt-2 text-4xl font-extrabold tracking-tight md:text-5xl">
          {heading}
        </h2>
      </div>

      <div className="mx-auto mt-8 w-full max-w-[900px] px-4 md:px-6">
        <div
          role="listbox"
          aria-label="Featured stories"
          className="flex w-full flex-col items-stretch gap-2 overflow-hidden md:h-[400px] md:flex-row md:gap-0"
        >
          {resolved.map((option, index) => {
            const isActive = activeIndex === index
            const entered = animatedOptions.includes(index)
            const Icon = option.Icon ?? Sparkles
            return (
              <div
                key={option.id ?? index}
                role="option"
                tabIndex={0}
                aria-selected={isActive}
                aria-label={`${option.title} — ${option.description ?? ''}`}
                onClick={() => handleOptionClick(index)}
                onKeyDown={(e) => handleKeyDown(e, index)}
                className="option relative flex cursor-pointer flex-col justify-end overflow-hidden transition-all duration-700 ease-in-out focus-visible:outline-2"
                style={{
                  backgroundImage: `url('${option.image}')`,
                  backgroundSize: isActive ? 'auto 100%' : 'auto 120%',
                  backgroundPosition: 'center',
                  backfaceVisibility: 'hidden',
                  opacity: entered ? 1 : 0,
                  transform: entered ? 'translateX(0)' : 'translateX(-60px)',
                  minWidth: '60px',
                  minHeight: isActive ? '320px' : '96px',
                  margin: 0,
                  borderRadius: '16px',
                  borderWidth: '1px',
                  borderStyle: 'solid',
                  borderColor: isActive ? 'var(--fg)' : 'var(--line)',
                  backgroundColor: 'var(--card)',
                  flex: isActive ? '7 1 0%' : '1 1 0%',
                  zIndex: isActive ? 10 : 1,
                  willChange: 'flex-grow, background-size, background-position',
                }}
              >
                {/* Bottom shadow for legibility */}
                <div
                  aria-hidden="true"
                  className="pointer-events-none absolute inset-x-0 bottom-0 transition-all duration-700 ease-in-out"
                  style={{
                    height: '60%',
                    background: isActive
                      ? 'linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.45) 55%, transparent 100%)'
                      : 'linear-gradient(to top, rgba(0,0,0,0.55) 0%, transparent 70%)',
                  }}
                />

                {/* Label with icon + info */}
                <div className="absolute inset-x-0 bottom-4 z-[2] flex w-full items-center justify-start gap-3 px-4">
                  <div
                    aria-hidden="true"
                    className="glass-nav flex h-[44px] w-[44px] min-w-[44px] items-center justify-center rounded-full transition-all duration-200"
                  >
                    <Icon className="h-5 w-5 text-white" />
                  </div>
                  <div className="min-w-0 flex-1 whitespace-normal text-left text-white">
                    {option.topic ? (
                      <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/70">
                        {option.topic}
                        {typeof option.consensus === 'number' ? ` • ${option.consensus}% consensus` : ''}
                      </p>
                    ) : null}
                    <p
                      className="truncate font-display text-lg font-bold leading-tight transition-all duration-700 ease-in-out md:whitespace-pre"
                      style={{
                        opacity: isActive ? 1 : 0,
                        transform: isActive ? 'translateX(0)' : 'translateX(25px)',
                      }}
                    >
                      {option.title}
                    </p>
                    <p
                      className="mt-0.5 line-clamp-2 text-sm text-white/80 transition-all duration-700 ease-in-out"
                      style={{
                        opacity: isActive ? 1 : 0,
                        transform: isActive ? 'translateX(0)' : 'translateX(25px)',
                      }}
                    >
                      {option.description}
                    </p>
                    {isActive && option.id && onOpen ? (
                      <span className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-white px-3.5 py-1.5 text-xs font-semibold text-black">
                        Read story
                        <ArrowRight className="h-3.5 w-3.5" />
                      </span>
                    ) : null}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Entrance animations (plain <style>: Vite has no <style jsx>) */}
      <style>{`
        @keyframes fadeInFromTop {
          0% { opacity: 0; transform: translateY(-20px); }
          100% { opacity: 1; transform: translateY(0); }
        }
        .animate-fadeInTop {
          opacity: 0;
          transform: translateY(-20px);
          animation: fadeInFromTop 0.8s ease-in-out forwards;
        }
        .delay-300 { animation-delay: 0.3s; }
        .delay-600 { animation-delay: 0.6s; }
        @media (min-width: 768px) {
          #root .option { border-radius: 0 !important; }
          #root .option:first-child { border-radius: 16px 0 0 16px !important; }
          #root .option:last-child { border-radius: 0 16px 16px 0 !important; }
        }
        @media (prefers-reduced-motion: reduce) {
          .animate-fadeInTop { animation-duration: 200ms; animation-delay: 0ms; }
          #root .option { transition-duration: 200ms; }
        }
      `}</style>
    </section>
  )
}

export { FALLBACK_ITEMS }
