const today = new Date().toLocaleDateString('en-US', {
  weekday: 'long',
  year: 'numeric',
  month: 'long',
  day: 'numeric',
})
const shortDate = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })

export default function NewsletterMasthead({ ticker = [] }) {
  return (
    <header className="px-6 pt-10 md:px-12 md:pt-14">
      <div className="mx-auto max-w-6xl">
        {/* Folio bar */}
        <div className="t-border flex items-center justify-between gap-4 border-b pb-2 text-[11px] font-medium uppercase tracking-[0.16em]">
          <span className="t-muted">Vol. I, No. 14</span>
          <time dateTime={new Date().toISOString()} className="t-muted hidden sm:inline">
            {today}
          </time>
          <span className="t-muted sm:hidden">{shortDate}</span>
          <span className="t-muted hidden md:inline">Late Edition</span>
          <span className="t-fg font-semibold">Free to your inbox</span>
        </div>

        {/* Masthead */}
        <div className="grid grid-cols-1 items-center gap-4 py-6 md:grid-cols-[1fr_auto_1fr] md:py-8">
          <div className="t-muted hidden text-[11px] leading-relaxed md:block">
            <p className="font-semibold uppercase tracking-[0.18em]">Est. 2026</p>
            <p className="mt-1">Cross-checked by agents.</p>
            <p>Sources always shown.</p>
          </div>
          <div className="text-center">
            <p className="kicker">WeAware presents</p>
            <h1 className="masthead-title mt-2 text-[clamp(2.6rem,7vw,5.2rem)]">The Crosscheck</h1>
            <p className="t-muted mt-2 text-[13px] font-medium tracking-wide">
              The feed, distilled. Disagreement kept in.
            </p>
          </div>
          <div className="t-muted hidden text-right text-[11px] leading-relaxed md:block">
            <p className="font-semibold uppercase tracking-[0.18em]">Morning paper</p>
            <p className="mt-1">Consensus scored.</p>
            <p>No outrage ranking.</p>
          </div>
        </div>

        {/* Thick-thin double rule */}
        <div className="rule-double-wrap" aria-hidden="true">
          <div className="rule-thick" />
          <div className="rule-thin" />
        </div>

        {/* Dateline ticker */}
        <div className="t-border mt-3 flex items-center gap-6 overflow-x-auto border-b pb-3 text-[12px]">
          <span className="t-fg shrink-0 font-semibold uppercase tracking-[0.14em]">Front page</span>
          <span className="t-muted shrink-0">WeAware, Global, {shortDate}</span>
          {ticker.map((t) => (
            <span key={t.id} className="t-muted shrink-0">
              <span className="t-fg font-semibold">{t.consensus}%</span> &middot; {t.title}
            </span>
          ))}
        </div>
      </div>
    </header>
  )
}
