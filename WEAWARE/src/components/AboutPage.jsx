import {
  ArrowRight,
  AudioLines,
  BookOpenText,
  Check,
  CircleHelp,
  Mail,
  Newspaper,
  Radio,
  Scale,
  ShieldCheck,
} from 'lucide-react'

const principles = [
  {
    number: '01',
    icon: Newspaper,
    title: 'Start with reporting',
    body: 'We bring together coverage from named outlets and link each story back to its original reporting. The summary is a starting point, not a substitute for the source.',
  },
  {
    number: '02',
    icon: Scale,
    title: 'Compare the accounts',
    body: 'We organize what sources corroborate, where they add context, and where their accounts differ. More links do not automatically mean more independent evidence.',
  },
  {
    number: '03',
    icon: ShieldCheck,
    title: 'Keep uncertainty visible',
    body: 'We call attention to claims that need context and show the evidence behind the coverage. You stay in control of what to conclude.',
  },
]

const products = [
  {
    icon: BookOpenText,
    eyebrow: 'Read',
    title: 'A feed with the sources in reach.',
    body: 'Browse current stories by topic, open the original links, and follow the coverage behind each summary.',
    action: 'Explore the feed',
    destination: 'feed',
  },
  {
    icon: Mail,
    eyebrow: 'Follow',
    title: 'The Crosscheck, on your schedule.',
    body: 'Choose the topics you care about and receive a daily or weekly email briefing when new coverage is available.',
    action: 'See newsletters',
    destination: 'newsletters',
  },
  {
    icon: AudioLines,
    eyebrow: 'Listen',
    title: 'Briefings made for listening.',
    body: 'Play article narration and published podcast episodes, with source notes available alongside the audio.',
    action: 'Listen to a briefing',
    destination: 'podcasts',
  },
]

export default function AboutPage({ onNavigate, stories = [] }) {
  const topicCount = new Set(stories.map((story) => story.topic).filter(Boolean)).size

  return (
    <main className="page-enter">
      <section className="px-6 pb-12 pt-12 md:px-12 md:pb-16 md:pt-20">
        <div className="mx-auto max-w-6xl">
          <div className="grid gap-10 border-b border-[var(--line)] pb-10 md:grid-cols-[minmax(0,1fr)_19rem] md:items-end md:gap-16 md:pb-14">
            <div>
              <p className="eyebrow-kanit t-muted text-xs">About WeAware <span className="t-faint px-2">/</span> A clearer view of the news</p>
              <h1 className="font-display mt-5 max-w-4xl text-5xl font-medium leading-[0.98] tracking-[-0.045em] md:text-7xl">
                News is a set of accounts. <span className="t-muted">Read across them.</span>
              </h1>
              <p className="t-muted font-body-serif mt-6 max-w-2xl text-lg leading-relaxed md:text-xl">
                WeAware brings coverage of the same story together, so you can see what reporting supports, where perspectives differ, and what still needs context.
              </p>
            </div>

            <aside aria-label="What WeAware helps you see" className="t-card relative overflow-hidden rounded-2xl border p-5 md:p-6">
              <div className="flex items-center justify-between">
                <span className="article-section-label">Across the coverage</span>
                <span className="t-faint font-mono text-[10px] tracking-[0.16em]">WEAWARE / 01</span>
              </div>
              <div className="t-border mt-6 border-t">
                {[
                  ['Shared ground', 'What multiple reports support'],
                  ['Different angles', 'What each account adds'],
                  ['Open questions', 'What the reporting cannot settle'],
                ].map(([label, detail], index) => (
                  <div key={label} className="t-border flex items-start gap-3 border-b py-3.5">
                    <span className="t-faint mt-0.5 font-mono text-[11px]">0{index + 1}</span>
                    <div>
                      <p className="text-sm font-semibold">{label}</p>
                      <p className="t-muted mt-0.5 text-xs">{detail}</p>
                    </div>
                    <Check className="t-muted ml-auto mt-1 h-3.5 w-3.5" aria-hidden="true" />
                  </div>
                ))}
              </div>
              <p className="t-faint mt-4 text-[11px] leading-relaxed">A reading guide, not a scorecard. Agreement is a signal to inspect, not proof.</p>
            </aside>
          </div>

          <div className="flex flex-wrap gap-x-10 gap-y-4 pt-5">
            <p className="t-muted text-xs"><span className="t-fg mr-2 font-semibold">{stories.length}</span> stories currently loaded</p>
            <p className="t-muted text-xs"><span className="t-fg mr-2 font-semibold">{topicCount}</span> topics in this view</p>
            <p className="t-muted ml-auto text-xs">Original reporting always stays one click away.</p>
          </div>
        </div>
      </section>

      <section aria-labelledby="how-we-work" className="px-6 py-10 md:px-12 md:py-14">
        <div className="mx-auto max-w-6xl">
          <div className="mb-8 grid gap-4 md:grid-cols-[1fr_22rem] md:items-end">
            <div>
              <p className="article-section-label">Our editorial approach</p>
              <h2 id="how-we-work" className="font-display mt-2 text-3xl font-medium tracking-tight md:text-4xl">Make the reporting easier to examine.</h2>
            </div>
            <p className="t-muted max-w-md text-sm leading-relaxed md:justify-self-end">We use technology to organize coverage and surface relationships between accounts. The point is to help you read with more context.</p>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {principles.map(({ number, icon: Icon, title, body }) => (
              <article key={number} className="stagger-item t-card t-border rounded-2xl border p-6 md:p-7" style={{ '--i': Number(number) - 1 }}>
                <div className="flex items-center justify-between">
                  <span className="t-faint font-mono text-xs tracking-[0.15em]">{number} / 03</span>
                  <Icon className="t-muted h-[18px] w-[18px]" aria-hidden="true" />
                </div>
                <h3 className="font-display mt-10 text-2xl font-medium tracking-tight">{title}</h3>
                <p className="t-muted mt-3 text-sm leading-relaxed">{body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section aria-labelledby="ways-to-read" className="px-6 py-10 md:px-12 md:py-14">
        <div className="mx-auto max-w-6xl">
          <div className="mb-8 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="article-section-label">One mission, a few ways in</p>
              <h2 id="ways-to-read" className="font-display mt-2 text-3xl font-medium tracking-tight md:text-4xl">Read, follow, or listen.</h2>
            </div>
            <p className="t-muted max-w-md text-sm leading-relaxed">Each format keeps the story connected to the reporting behind it.</p>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            {products.map(({ icon: Icon, eyebrow, title, body, action, destination }) => (
              <article key={destination} className="t-card t-border flex flex-col rounded-2xl border p-6 md:p-7">
                <div className="flex items-center gap-3">
                  <span className="t-border grid h-10 w-10 place-items-center rounded-full border"><Icon className="t-muted h-[18px] w-[18px]" aria-hidden="true" /></span>
                  <span className="article-section-label">{eyebrow}</span>
                </div>
                <h3 className="font-display mt-7 text-2xl font-medium leading-tight tracking-tight">{title}</h3>
                <p className="t-muted mt-3 flex-1 text-sm leading-relaxed">{body}</p>
                <button type="button" onClick={() => onNavigate(destination)} className="t-fg mt-7 inline-flex min-h-11 w-fit items-center gap-2 text-sm font-medium hover:opacity-70">
                  {action}<ArrowRight className="h-4 w-4" aria-hidden="true" />
                </button>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section aria-labelledby="confidence-note" className="px-6 py-10 md:px-12 md:py-14">
        <div className="t-card mx-auto grid max-w-6xl gap-8 rounded-2xl border p-6 md:grid-cols-[0.85fr_1.15fr] md:p-10">
          <div>
            <p className="article-section-label">A note on confidence</p>
            <h2 id="confidence-note" className="font-display mt-3 text-3xl font-medium tracking-tight md:text-4xl">A signal, not a verdict.</h2>
          </div>
          <div className="space-y-4">
            <p className="t-muted font-body-serif text-base leading-relaxed md:text-lg">
              Agreement across reviewed coverage can help you understand how widely a claim is reported. It does not prove the claim, measure every newsroom, or replace your judgment.
            </p>
            <p className="t-muted text-sm leading-relaxed">
              Sources may rely on the same underlying information, and coverage can be incomplete. Check publication dates, open the original links, and notice what is still unknown.
            </p>
            <div className="flex items-start gap-2 border-t border-[var(--line)] pt-4 text-sm">
              <CircleHelp className="t-muted mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <p className="t-muted">AI helps organize and summarize coverage and can make mistakes. Check important claims against the linked reporting.</p>
            </div>
          </div>
        </div>
      </section>

      <section aria-labelledby="keep-reading" className="px-6 pb-16 pt-6 md:px-12 md:pb-20">
        <div className="t-border mx-auto flex max-w-6xl flex-col gap-5 border-t pt-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="article-section-label">Keep reading</p>
            <h2 id="keep-reading" className="font-display mt-1 text-2xl font-medium">Follow the sources. Form your own view.</h2>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <button type="button" onClick={() => onNavigate('feed')} className="t-btn-primary flex min-h-11 items-center justify-center gap-2 rounded-full px-6 text-sm font-medium">
              Browse the feed <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </button>
            <button type="button" onClick={() => onNavigate('podcasts')} className="t-btn-outline flex min-h-11 items-center justify-center gap-2 rounded-full px-6 text-sm font-medium">
              <Radio className="h-4 w-4" aria-hidden="true" /> Listen to WeAware
            </button>
          </div>
        </div>
      </section>
    </main>
  )
}
