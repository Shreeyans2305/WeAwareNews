import { ArrowRight, Link2, Scale, ShieldCheck } from 'lucide-react'
import { stories } from '../data/stories.js'
import Reveal from './Reveal.jsx'
import DomainReserve from './DomainReserve.jsx'

const ACCENT = '#00F0FF'

const principles = [
  {
    icon: ShieldCheck,
    title: 'Cross-check before publish',
    body: 'Every story lists the outlets behind it. Agreement, added context, and disputes stay visible instead of averaged away.',
  },
  {
    icon: Scale,
    title: 'Show the split, not the spin',
    body: 'Consensus is a number with receipts. You see which sources corroborate and which ones challenge the headline.',
  },
  {
    icon: Link2,
    title: 'Link back to the reporting',
    body: 'Summaries never replace originals. Names, notes, and flagged claims point to the work reporters actually did.',
  },
]

export default function AboutPage({ onNavigate }) {
  return (
    <div className="page-enter">
      <section className="perspective-stage px-6 pb-10 pt-14 md:px-12 md:pt-20">
        <div className="max-w-3xl">
          <p className="stagger-item eyebrow-kanit text-[12px] text-white/50" style={{ '--i': 0 }}>
            About
          </p>
          <h1 className="stagger-item mt-3 font-display text-5xl font-extrabold leading-[1.02] tracking-tight text-white md:text-6xl" style={{ '--i': 1 }}>
            <span className="display-3d display-3d-gradient">News that admits when sources disagree.</span>
          </h1>
          <p className="stagger-item mt-4 max-w-xl font-display text-lg font-medium leading-relaxed text-white/70 md:text-xl" style={{ '--i': 2 }}>
            WeAware is a reading room for contested stories. Agents gather coverage,
            compare claims, and surface the split so you can judge what deserves confidence.
          </p>
        </div>
      </section>

      <section className="px-6 md:px-12">
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1.2fr_0.8fr]">
          <article
            className="stagger-item lift rounded-2xl border border-white/10 bg-white/[0.04] p-8 md:p-10"
            style={{ '--i': 3 }}
          >
            <div className="flex items-center gap-2.5">
              <ShieldCheck className="h-5 w-5" style={{ color: ACCENT }} />
              <h2 className="font-display text-2xl font-extrabold tracking-tight text-white">How a cross-check reads</h2>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-white/60">
              Open any story to find three layers. The summary in plain language, the
              consensus meter with source stances, and flagged claims with reasons you can verify.
            </p>
            <div className="mt-6 space-y-3">
              {principles.map((principle, index) => (
                <div
                  key={principle.title}
                  className={`flex gap-4 rounded-xl border border-white/10 bg-black/40 p-4 ${
                    index === 0 ? 'md:p-5' : ''
                  }`}
                >
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/5">
                    <principle.icon className="h-5 w-5" style={{ color: ACCENT }} />
                  </span>
                  <div>
                    <h3 className={`${index === 0 ? 'text-lg' : 'text-base'} font-display font-bold text-white`}>
                      {principle.title}
                    </h3>
                    <p className="mt-1 text-sm leading-relaxed text-white/55">{principle.body}</p>
                  </div>
                </div>
              ))}
            </div>
          </article>

          <aside className="stagger-item flex flex-col rounded-2xl border border-white/10 bg-black/50 p-8 md:p-10" style={{ '--i': 4 }}>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-white/50">
              From the live feed
            </p>
            <p className="mt-3 font-display text-6xl font-extrabold tracking-tight text-white">
              {stories.length}
            </p>
            <p className="mt-1 text-sm text-white/55">
              cross-checked stories across {new Set(stories.map((story) => story.topic)).size} topics,
              each with sources and flagged claims attached.
            </p>
            <ul className="mt-6 space-y-3 border-t border-white/10 pt-6">
              {stories.slice(0, 3).map((story) => (
                <li key={story.id} className="flex items-start justify-between gap-3 text-sm">
                  <span className="leading-snug text-white/70">{story.title}</span>
                  <span className="shrink-0 rounded-full bg-white/10 px-2.5 py-1 text-xs font-medium text-white">
                    {story.consensus}%
                  </span>
                </li>
              ))}
            </ul>
            <div className="mt-auto pt-8">
              <button
                type="button"
                onClick={() => onNavigate('feed')}
                className="flex w-full items-center justify-center gap-2 rounded-full bg-white px-6 py-2.5 text-sm font-medium text-black transition-colors hover:bg-white/85"
              >
                Browse the feed
                <ArrowRight className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => onNavigate('newsletters')}
                className="mt-2 w-full rounded-full border border-white/15 px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-white/10"
              >
                Get the Crosscheck email
              </button>
            </div>
          </aside>
        </div>
      </section>

      <Reveal className="px-6 py-12 md:px-12">
        <DomainReserve />
      </Reveal>

      <Reveal className="px-6 pb-12 md:px-12">
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-8 md:p-10">
          <h2 className="max-w-xl font-display text-3xl font-extrabold tracking-tight text-white">
            What we will not do
          </h2>
          <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-3">
            <div>
              <h3 className="text-sm font-semibold text-white">No hidden averaging</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-white/55">
                Disputes are labeled disputes. A low consensus score is information, not failure.
              </p>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">No outrage ranking</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-white/55">
                Stories are ordered by recency and topic, not by what keeps you scrolling.
              </p>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">No dead ends</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-white/55">
                Every claim worth doubting carries its reason in plain words, next to the sources.
              </p>
            </div>
          </div>
        </div>
      </Reveal>
    </div>
  )
}
