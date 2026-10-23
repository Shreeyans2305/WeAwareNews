import { ArrowRight, BookOpen, CircleHelp, ExternalLink, Scale, ShieldCheck } from 'lucide-react'
import Reveal from './Reveal.jsx'
import DomainReserve from './DomainReserve.jsx'

const steps = [
  {
    number: '01',
    icon: BookOpen,
    title: 'Start with reporting',
    body: 'We gather coverage from named outlets and link each story back to its original reporting, so you can read beyond the summary.',
  },
  {
    number: '02',
    icon: Scale,
    title: 'Compare the accounts',
    body: 'We line up what sources corroborate, where they add context, and where their accounts differ. A source count is not a vote on truth.',
  },
  {
    number: '03',
    icon: ShieldCheck,
    title: 'Show what needs care',
    body: 'Claims that need more context are called out with a reason. Follow the links and decide what the evidence supports.',
  },
]

export default function AboutPage({ onNavigate, stories = [] }) {
  const topicCount = new Set(stories.map((story) => story.topic).filter(Boolean)).size

  return (
    <main className="page-enter">
      <section className="px-6 pb-10 pt-14 md:px-12 md:pt-20">
        <div className="mx-auto grid max-w-6xl gap-8 border-b border-[var(--line)] pb-10 md:grid-cols-[minmax(0,1.4fr)_minmax(15rem,0.6fr)] md:items-end md:gap-16 md:pb-14">
          <div>
            <p className="stagger-item eyebrow-kanit t-muted text-xs" style={{ '--i': 0 }}>About WeAware</p>
            <h1 className="stagger-item masthead-title mt-4 max-w-4xl text-5xl md:text-7xl" style={{ '--i': 1 }}>
              Read the reporting. See the disagreement.
            </h1>
            <p className="stagger-item t-muted font-body-serif mt-5 max-w-2xl text-lg leading-relaxed md:text-xl" style={{ '--i': 2 }}>
              WeAware brings multiple accounts of a story into one clear reading experience, with sources and uncertainty kept in view.
            </p>
          </div>
          <div className="stagger-item t-border flex gap-8 border-t pt-5 md:justify-end md:border-l md:border-t-0 md:pl-8 md:pt-0" style={{ '--i': 3 }}>
            <div>
              <p className="font-display text-4xl font-bold">{stories.length}</p>
              <p className="t-muted mt-1 text-xs uppercase tracking-[0.13em]">Stories in the feed</p>
            </div>
            <div>
              <p className="font-display text-4xl font-bold">{topicCount}</p>
              <p className="t-muted mt-1 text-xs uppercase tracking-[0.13em]">Topics covered</p>
            </div>
          </div>
        </div>
      </section>

      <section aria-labelledby="how-we-work" className="px-6 py-8 md:px-12 md:py-12">
        <div className="mx-auto max-w-6xl">
          <div className="mb-7 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="article-section-label">Our approach</p>
              <h2 id="how-we-work" className="font-display mt-2 text-3xl font-bold tracking-tight md:text-4xl">A better way to compare coverage</h2>
            </div>
            <p className="t-muted max-w-md text-sm leading-relaxed">The goal is not to tell you what to think. It is to make it easier to see what the reporting says.</p>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {steps.map(({ number, icon: Icon, title, body }, index) => (
              <article key={number} className="stagger-item t-card t-border rounded-2xl border p-6 md:p-7" style={{ '--i': index }}>
                <div className="flex items-center justify-between">
                  <span className="t-faint font-display text-3xl font-semibold">{number}</span>
                  <Icon className="t-muted h-5 w-5" aria-hidden="true" />
                </div>
                <h3 className="font-display mt-8 text-2xl font-bold tracking-tight">{title}</h3>
                <p className="t-muted mt-2 text-sm leading-relaxed">{body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <Reveal className="px-6 py-10 md:px-12 md:py-14">
        <section aria-labelledby="read-with-care" className="t-card mx-auto grid max-w-6xl gap-8 rounded-2xl border p-6 md:grid-cols-[0.8fr_1.2fr] md:p-10">
          <div>
            <p className="article-section-label">A note on confidence</p>
            <h2 id="read-with-care" className="font-display mt-3 text-3xl font-bold tracking-tight">A signal, not a verdict.</h2>
          </div>
          <div className="space-y-4">
            <p className="t-muted font-body-serif text-base leading-relaxed md:text-lg">
              Consensus describes how much the reviewed coverage agrees on a claim. It does not prove a claim is true, measure every newsroom, or replace your judgment.
            </p>
            <p className="t-muted text-sm leading-relaxed">
              Sources can share the same underlying information, and coverage can be incomplete. Open the original links, check the dates, and pay attention to what is still unknown.
            </p>
            <div className="flex items-start gap-2 border-t border-[var(--line)] pt-4 text-sm">
              <CircleHelp className="t-muted mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <p className="t-muted">AI helps organize and summarize coverage. It can make mistakes, so important claims should be checked against the linked reporting.</p>
            </div>
          </div>
        </section>
      </Reveal>

      <Reveal className="px-6 pb-10 md:px-12">
        <DomainReserve />
      </Reveal>

      <section className="px-6 pb-14 md:px-12">
        <div className="t-border mx-auto flex max-w-6xl flex-col gap-5 border-t pt-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="article-section-label">Keep reading</p>
            <h2 className="font-display mt-1 text-2xl font-bold">Make up your own mind.</h2>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <button type="button" onClick={() => onNavigate('feed')} className="t-btn-primary flex items-center justify-center gap-2 rounded-full px-6 py-3 text-sm font-medium">
              Browse the feed <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </button>
            <button type="button" onClick={() => onNavigate('newsletters')} className="t-btn-outline flex items-center justify-center gap-2 rounded-full px-6 py-3 text-sm font-medium">
              Explore The Crosscheck <ExternalLink className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      </section>
    </main>
  )
}
