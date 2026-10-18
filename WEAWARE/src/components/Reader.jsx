import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, ArrowRight, CheckCircle2, Headphones, Pause, Share2, ShieldCheck, TriangleAlert } from 'lucide-react'
import { listenMinsFor } from './ListenBar.jsx'
import ShareSheet from './ShareSheet.jsx'
import { TimelineContent } from './ui/timeline-animation.jsx'
import { VerticalCutReveal } from './ui/vertical-cut-reveal.jsx'
import StoryArtwork from './StoryArtwork.jsx'

export default function Reader({ story, onBack, onListen, isListening, listeningPlaying }) {
  const heroRef = useRef(null)
  const [meter, setMeter] = useState(0)
  const [shareOpen, setShareOpen] = useState(false)

  useEffect(() => {
    const frame = requestAnimationFrame(() => requestAnimationFrame(() => setMeter(story.consensus)))
    return () => cancelAnimationFrame(frame)
  }, [story.consensus])

  const revealVariants = {
    visible: (i) => ({ y: 0, opacity: 1, filter: 'blur(0px)', transition: { delay: i * 0.12, duration: 0.5 } }),
    hidden: { filter: 'blur(10px)', y: -20, opacity: 0 },
  }
  const scaleVariants = {
    visible: (i) => ({ opacity: 1, filter: 'blur(0px)', transition: { delay: i * 0.12, duration: 0.5 } }),
    hidden: { filter: 'blur(10px)', opacity: 0 },
  }

  const clipId = `clip-article-${story.id.replace(/[^a-zA-Z0-9]/g, '')}`
  return (
    <article ref={heroRef} className="page-enter t-bg">
      <div className="mx-auto max-w-6xl px-4 py-8 md:px-8">
        <button type="button" onClick={onBack} className="t-btn-outline mb-6 flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium">
          <ArrowLeft className="h-4 w-4" />
          Back to feed
        </button>

        <div className="relative">
          <div className="absolute z-10 mb-8 flex w-[85%] items-center justify-between lg:top-4 md:top-0 sm:-top-2 -top-3">
            <div className="flex items-center gap-2 text-xl">
              <span className="signal-dot h-2 w-2 rounded-full" />
              <TimelineContent as="span" animationNum={0} timelineRef={heroRef} customVariants={revealVariants} className="eyebrow-kanit text-[12px]">
                {story.topic} • {story.publishedAt}
              </TimelineContent>
            </div>
            <div className="flex gap-3">
              <TimelineContent
                as="button"
                type="button"
                animationNum={1}
                timelineRef={heroRef}
                customVariants={revealVariants}
                onClick={() => onListen && onListen(story.id)}
                aria-label={isListening && listeningPlaying ? `Pause audiobook for ${story.title}` : `Listen to ${story.title}`}
                className="t-btn-outline flex h-8 w-8 items-center justify-center rounded-lg"
              >
                {isListening && listeningPlaying ? <Pause className="h-4 w-4" /> : <Headphones className="h-4 w-4" />}
              </TimelineContent>
              <TimelineContent
                as="button"
                type="button"
                animationNum={2}
                timelineRef={heroRef}
                customVariants={revealVariants}
                onClick={() => setShareOpen(true)}
                aria-label={`Share ${story.title}`}
                className="t-btn-outline flex h-8 w-8 items-center justify-center rounded-lg"
              >
                <Share2 className="h-4 w-4" />
              </TimelineContent>
              <TimelineContent as="span" animationNum={3} timelineRef={heroRef} customVariants={revealVariants} className="t-btn-outline hidden h-8 items-center rounded-lg px-3 text-xs font-medium sm:flex">
                {story.consensus}% consensus
              </TimelineContent>
            </div>
          </div>

          <TimelineContent as="figure" animationNum={4} timelineRef={heroRef} customVariants={scaleVariants} className="relative">
            {story.image ? <>
            <svg className="w-full" width="100%" height="100%" viewBox="0 0 100 40" role="img" aria-label={story.title}>
              <defs>
                <clipPath id={clipId} clipPathUnits="objectBoundingBox">
                  <path
                    d="M0.0998072 1H0.422076H0.749756C0.767072 1 0.774207 0.961783 0.77561 0.942675V0.807325C0.777053 0.743631 0.791844 0.731953 0.799059 0.734076H0.969813C0.996268 0.730255 1.00088 0.693206 0.999875 0.675159V0.0700637C0.999875 0.0254777 0.985045 0.00477707 0.977629 0H0.902473C0.854975 0 0.890448 0.138535 0.850165 0.138535H0.0204424C0.00408849 0.142357 0 0.180467 0 0.199045V0.410828C0 0.449045 0.0136283 0.46603 0.0204424 0.469745H0.0523086C0.0696245 0.471019 0.0735527 0.497877 0.0733523 0.511146V0.915605C0.0723903 0.983121 0.090588 1 0.0998072 1Z"
                    fill="#D9D9D9"
                  />
                </clipPath>
              </defs>
              <image clipPath={`url(#${clipId})`} preserveAspectRatio="xMidYMid slice" width="100%" height="100%" href={story.image} />
            </svg>
            <figcaption className="t-faint mt-2 text-right text-[11px]">Source image</figcaption>
            </> : <div className="aspect-[5/2] overflow-hidden rounded-xl"><StoryArtwork story={story} /></div>}
          </TimelineContent>

          <div className="flex flex-wrap items-center justify-between py-3 text-sm">
            <TimelineContent as="div" animationNum={5} timelineRef={heroRef} customVariants={revealVariants} className="flex gap-4">
              <div className="mb-2 flex items-center gap-2 text-xs sm:text-base">
                <span className="font-bold">{story.readMins} min</span>
                <span className="t-muted">read</span>
                <span className="t-faint">|</span>
              </div>
              <div className="mb-2 flex items-center gap-2 text-xs sm:text-base">
                <span className="font-bold">{listenMinsFor(story)} min</span>
                <span className="t-muted">listen</span>
              </div>
            </TimelineContent>
            <div className="bottom-16 right-0 flex flex-row-reverse gap-4 lg:absolute lg:flex-col lg:gap-0">
              <TimelineContent as="div" animationNum={6} timelineRef={heroRef} customVariants={revealVariants} className="mb-2 flex items-center gap-2 text-2xl sm:text-3xl lg:text-4xl">
                <span className="font-semibold">{story.consensus}%</span>
                <span className="t-muted uppercase">consensus</span>
              </TimelineContent>
              <TimelineContent as="div" animationNum={7} timelineRef={heroRef} customVariants={revealVariants} className="mb-2 flex items-center gap-2 text-xs sm:text-base">
                <span className="font-bold">{story.sources.length}</span>
                <span className="t-muted">sources cross-checked</span>
                <span className="t-faint lg:hidden">|</span>
              </TimelineContent>
            </div>
          </div>
        </div>

        <div className="grid gap-8 md:grid-cols-3">
          <div className="md:col-span-2">
            <h1 className="mb-6 font-display text-2xl font-extrabold !leading-[110%] tracking-tight sm:text-4xl md:text-5xl">
              <VerticalCutReveal splitBy="words" staggerDuration={0.06} staggerFrom="first" reverse={true} transition={{ type: 'spring', stiffness: 250, damping: 30, delay: 0.4 }}>
                {story.title}
              </VerticalCutReveal>
            </h1>
            <TimelineContent as="p" animationNum={8} timelineRef={heroRef} customVariants={revealVariants} className="t-muted mb-8 font-display text-lg font-medium leading-relaxed md:text-xl">
              {story.summary}
            </TimelineContent>
            <TimelineContent as="div" animationNum={9} timelineRef={heroRef} customVariants={revealVariants} className="max-w-3xl space-y-5 break-words text-sm sm:text-base [overflow-wrap:anywhere]">
              {story.body.map((paragraph, i) => (
                <p key={`body-${i}`} className={`${i === 0 ? '' : 't-muted '}leading-8`}>{paragraph}</p>
              ))}
            </TimelineContent>
          </div>

          <div className="md:col-span-1">
            <div className="text-right">
              <TimelineContent as="div" animationNum={12} timelineRef={heroRef} customVariants={revealVariants} className="mb-2 font-display text-2xl font-extrabold tracking-tight">
                WEAWARE
              </TimelineContent>
              <TimelineContent as="div" animationNum={13} timelineRef={heroRef} customVariants={revealVariants} className="t-muted mb-8 text-sm">
                Cross-checked • {story.sources.length} sources • {story.publishedAt}
              </TimelineContent>
              <TimelineContent as="div" animationNum={14} timelineRef={heroRef} customVariants={revealVariants} className="mb-6">
                <p className="mb-4 font-medium">Prefer to listen? AI voice, full story.</p>
              </TimelineContent>
              <TimelineContent
                as="button"
                type="button"
                animationNum={15}
                timelineRef={heroRef}
                customVariants={revealVariants}
                onClick={() => onListen && onListen(story.id)}
                className="t-btn-primary ml-auto flex w-fit cursor-pointer items-center gap-2 rounded-lg px-5 py-3 font-semibold"
              >
                {isListening && listeningPlaying ? 'PAUSE AUDIO' : `LISTEN • ${listenMinsFor(story)} MIN`} {isListening && listeningPlaying ? <Pause /> : <ArrowRight />}
              </TimelineContent>
              <TimelineContent
                as="button"
                type="button"
                animationNum={15}
                timelineRef={heroRef}
                customVariants={revealVariants}
                onClick={() => setShareOpen(true)}
                className="t-btn-outline ml-auto mt-3 flex w-fit items-center gap-2 rounded-lg px-5 py-2.5 text-sm"
              >
                <Share2 className="h-4 w-4" /> Share story
              </TimelineContent>
              <p className="t-faint mt-3 text-xs">AI voice • mock audio • weaware.news/s/{story.id}</p>
            </div>
          </div>
        </div>

        <section className="t-card mt-10 rounded-2xl border p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <ShieldCheck className="h-5 w-5" />
              <h2 className="font-display text-xl font-extrabold tracking-tight">Cross-checked by WeAware agents</h2>
            </div>
            <span className="t-btn-outline rounded-full px-3 py-1 text-xs font-medium">{story.sources.length} sources</span>
          </div>
          <div className="mt-5">
            <div className="flex items-center justify-between text-sm">
              <span className="t-muted">Source consensus</span>
              <span className="font-semibold">{story.consensus}%</span>
            </div>
            <div className="t-card mt-2 h-2 overflow-hidden rounded-full border">
              <div className="h-full rounded-full" style={{ width: `${meter}%`, background: 'var(--fg)' }} />
            </div>
          </div>
          <ul className="t-border mt-5 space-y-3.5 border-t pt-5">
            {story.sources.map((source) => (
              <li key={source.outlet} className="flex items-start gap-3">
                <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ background: 'var(--fg)' }} />
                <div>
                  <p className="text-sm font-medium">
                    {source.url ? <a className="underline underline-offset-2" href={source.url} target="_blank" rel="noreferrer">{source.outlet}</a> : source.outlet}
                    <span className="t-faint ml-2 text-xs font-normal capitalize">
                      {source.stance === 'agree' ? 'corroborates' : source.stance === 'context' ? 'adds context' : 'disputes'}
                    </span>
                  </p>
                  <p className="t-muted mt-0.5 text-sm leading-relaxed">{source.note}</p>
                </div>
              </li>
            ))}
          </ul>
          <div className="t-border mt-5 border-t pt-5">
            {story.flaggedClaims.length === 0 ? (
              <p className="t-muted flex items-center gap-2 text-sm">
                <CheckCircle2 className="h-4 w-4" />
                No low-confidence claims flagged in this story.
              </p>
            ) : (
              <ul className="space-y-3">
                {story.flaggedClaims.map((flag, i) => (
                  <li key={i} className="t-card rounded-xl border p-4">
                    <p className="flex items-start gap-2 text-sm font-medium">
                      <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
                      {flag.claim}
                    </p>
                    <p className="t-muted mt-1.5 pl-6 text-sm leading-relaxed">{flag.reason}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>
      <ShareSheet story={story} open={shareOpen} onClose={() => setShareOpen(false)} />
    </article>
  )
}
