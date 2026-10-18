import { ArrowRight, Link2, Scale, ShieldCheck } from 'lucide-react'
import Reveal from './Reveal.jsx'
import DomainReserve from './DomainReserve.jsx'

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

export default function AboutPage({ onNavigate, stories = [] }) {
  return (
    <div className="page-enter">
      <section className="px-6 pb-10 pt-14 md:px-12 md:pt-20">
        <div className="max-w-3xl">
          <p className="stagger-item eyebrow-kanit t-muted text-[12px]" style={{ '--i': 0 }}>About</p>
          <h1 className="stagger-item mt-3 font-display text-5xl font-extrabold leading-[1.02] tracking-tight md:text-6xl" style={{ '--i': 1 }}>
            News that admits when sources disagree.
          </h1>
          <p className="stagger-item t-muted mt-4 max-w-xl font-display text-lg font-medium leading-relaxed md:text-xl" style={{ '--i': 2 }}>
            WeAware is a reading room for contested stories. Agents gather coverage, compare claims, and surface the
            split so you can judge what deserves confidence.
          </p>
        </div>
      </section>

      <section className="px-6 md:px-12">
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1.2fr_0.8fr]">
          <article className="stagger-item t-card rounded-2xl border p-8 md:p-10" style={{ '--i': 3 }}>
            <div className="flex items-center gap-2.5">
              <ShieldCheck className="h-5 w-5" />
              <h2 className="font-display text-2xl font-extrabold tracking-tight">How a cross-check reads</h2>
            </div>
            <p className="t-muted mt-3 text-sm leading-relaxed">
              Open any story to find three layers. The summary in plain language, the consensus meter with source
              stances, and flagged claims with reasons you can verify.
            </p>
            <div className="mt-6 space-y-3">
              {principles.map((principle) => (
                <div key={principle.title} className="t-card t-border flex gap-4 rounded-xl border p-4">
                  <span className="t-btn-outline flex h-10 w-10 shrink-0 items-center justify-center rounded-full">
                    <principle.icon className="h-5 w-5" />
                  </span>
                  <div>
                    <h3 className="font-display text-base font-bold">{principle.title}</h3>
                    <p className="t-muted mt-1 text-sm leading-relaxed">{principle.body}</p>
                  </div>
                </div>
              ))}
            </div>
          </article>

          <aside className="stagger-item t-card flex flex-col rounded-2xl border p-8 md:p-10" style={{ '--i': 4 }}>
            <p className="t-muted text-[11px] font-semibold uppercase tracking-[0.18em]">From the live feed</p>
            <p className="mt-3 font-display text-6xl font-extrabold tracking-tight">{stories.length}</p>
            <p className="t-muted mt-1 text-sm">
              cross-checked stories across {new Set(stories.map((story) => story.topic)).size} topics, each with
              sources and flagged claims attached.
            </p>
            <ul className="t-border mt-6 space-y-3 border-t pt-6">
              {stories.slice(0, 3).map((story) => (
                <li key={story.id} className="flex items-start justify-between gap-3 text-sm">
                  <span className="leading-snug">{story.title}</span>
                  <span className="t-btn-primary shrink-0 rounded-full px-2.5 py-1 text-xs font-medium">{story.consensus}%</span>
                </li>
              ))}
            </ul>
            <div className="mt-auto pt-8">
              <button type="button" onClick={() => onNavigate('feed')} className="t-btn-primary flex w-full items-center justify-center gap-2 rounded-full px-6 py-2.5 text-sm font-medium">
                Browse the feed
                <ArrowRight className="h-4 w-4" />
              </button>
              <button type="button" onClick={() => onNavigate('newsletters')} className="t-btn-outline mt-2 w-full rounded-full px-6 py-2.5 text-sm font-medium">
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
        <div className="t-card rounded-2xl border p-8 md:p-10">
          <h2 className="max-w-xl font-display text-3xl font-extrabold tracking-tight">What we will not do</h2>
          <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-3">
            <div>
              <h3 className="text-sm font-semibold">No hidden averaging</h3>
              <p className="t-muted mt-1.5 text-sm leading-relaxed">Disputes are labeled disputes. A low consensus score is information, not failure.</p>
            </div>
            <div>
              <h3 className="text-sm font-semibold">No outrage ranking</h3>
              <p className="t-muted mt-1.5 text-sm leading-relaxed">Stories are ordered by recency and topic, not by what keeps you scrolling.</p>
            </div>
            <div>
              <h3 className="text-sm font-semibold">No dead ends</h3>
              <p className="t-muted mt-1.5 text-sm leading-relaxed">Every claim worth doubting carries its reason in plain words, next to the sources.</p>
            </div>
          </div>
        </div>
      </Reveal>
    </div>
  )
}
