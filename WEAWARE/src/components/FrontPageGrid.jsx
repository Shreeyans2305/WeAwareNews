function Byline({ story }) {
  return (
    <p className="byline mt-3">
      By WeAware Agents &middot; {story.readMins} min read &middot; {story.sources.length} sources &middot;{' '}
      {story.publishedAt}
    </p>
  )
}

export default function FrontPageGrid({ stories, onOpenStory }) {
  if (!stories || stories.length === 0) return null
  const lead = stories[0]
  const stackTop = stories[4] ?? stories[1]
  const stackBottom = stories[6] ?? stories[2]
  const row = [stories[3], stories[8], stories[9]].filter(Boolean)
  const leadFlag = lead.flaggedClaims?.[0]

  return (
    <section aria-label="Front page stories" className="px-6 md:px-12">
      <div className="mx-auto max-w-6xl">
        <div className="grid grid-cols-1 gap-10 py-8 lg:grid-cols-12 lg:gap-0">
          {/* Lead story */}
          <article className="lg:col-span-7 lg:pr-8">
            <p className="kicker">Top story, {lead.topic}</p>
            <h2 className="headline-serif mt-2 text-4xl md:text-5xl">
              <button type="button" onClick={() => onOpenStory(lead.id)} className="text-left">
                {lead.title}
              </button>
            </h2>
            <Byline story={lead} />
            <figure className="mt-5">
              <div className="t-border overflow-hidden border">
                <img
                  src={lead.image}
                  alt={lead.title}
                  loading="lazy"
                  className="newspaper-img aspect-[16/9] w-full object-cover"
                />
              </div>
              <figcaption className="t-faint mt-2 text-xs leading-relaxed">
                {lead.summary} <span className="t-muted">Photo: WeAware demo archive.</span>
              </figcaption>
            </figure>
            <div className="article-justify article-columns-2 font-body-serif mt-5 text-[15px] leading-[1.75]">
              <p className="drop-cap">{lead.body?.[0]}</p>
              <p className="mt-3">{lead.body?.[1]}</p>
            </div>
            <div className="mt-5 flex flex-wrap items-center gap-3">
              <span className="stamp">{lead.consensus}% agree</span>
              <span className="t-muted text-xs">{lead.sources.length} sources cross-checked</span>
              <button
                type="button"
                onClick={() => onOpenStory(lead.id)}
                className="t-btn-outline ml-auto px-5 py-2 text-sm font-medium"
              >
                Read full cross-check
              </button>
            </div>
          </article>

          {/* Stack column */}
          <div className="t-border flex flex-col gap-8 border-t pt-8 lg:col-span-5 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
            {[stackTop, stackBottom].map((s) => (
              <article key={s.id} className="border-b pb-8 last:border-b-0 last:pb-0 t-border">
                <p className="kicker">{s.topic}</p>
                <h3 className="headline-serif mt-2 text-2xl">
                  <button type="button" onClick={() => onOpenStory(s.id)} className="text-left">
                    {s.title}
                  </button>
                </h3>
                <Byline story={s} />
                <div className="t-border mt-3 overflow-hidden border">
                  <img
                    src={s.image}
                    alt={s.title}
                    loading="lazy"
                    className="newspaper-img aspect-[16/10] w-full object-cover"
                  />
                </div>
                <p className="t-muted mt-3 text-sm leading-relaxed">{s.summary}</p>
                <div className="mt-3 flex items-center gap-3">
                  <span className="stamp">{s.consensus}% agree</span>
                  <button
                    type="button"
                    onClick={() => onOpenStory(s.id)}
                    className="t-muted text-sm font-medium underline underline-offset-4"
                  >
                    Continue on page 2
                  </button>
                </div>
              </article>
            ))}

            {/* Pull quote / disagreement box */}
            {leadFlag && (
              <aside className="t-border border p-5" aria-label="Disagreement kept in">
                <p className="kicker">Disagreement kept in</p>
                <blockquote className="font-body-serif mt-2 text-lg italic leading-snug">
                  &ldquo;{leadFlag.claim}&rdquo;
                </blockquote>
                <p className="t-muted mt-2 text-sm">{leadFlag.reason}</p>
              </aside>
            )}
          </div>
        </div>

        {/* Secondary row */}
        {row.length > 0 && (
          <div className="t-border grid grid-cols-1 gap-8 border-t py-8 md:grid-cols-3 md:gap-0">
            {row.map((s, idx) => (
              <article
                key={s.id}
                className={
                  'md:px-6 ' +
                  (idx === 0 ? 'md:pl-0 ' : '') +
                  (idx === row.length - 1 ? 'md:pr-0 ' : '') +
                  (idx > 0 ? 't-border md:border-l ' : '') +
                  'border-t pt-6 md:border-t-0 md:pt-0'
                }
              >
                <p className="kicker">{s.topic}</p>
                <h3 className="headline-serif mt-2 text-xl leading-tight">
                  <button type="button" onClick={() => onOpenStory(s.id)} className="text-left">
                    {s.title}
                  </button>
                </h3>
                <p className="t-muted mt-2 line-clamp-3 text-sm leading-relaxed">{s.summary}</p>
                <p className="mt-3 flex items-center gap-2 text-xs">
                  <span className="stamp">{s.consensus}%</span>
                  <span className="t-faint">
                    {s.readMins} min &middot; {s.publishedAt}
                  </span>
                </p>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
