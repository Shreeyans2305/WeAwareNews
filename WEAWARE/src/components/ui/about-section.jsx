import { useRef } from 'react'
import { TimelineContent } from './timeline-animation.jsx'
import { VerticalCutReveal } from './vertical-cut-reveal.jsx'
import { ArrowRight, Facebook, Instagram, Linkedin, Youtube } from 'lucide-react'

const HERO_IMAGE =
  'https://images.unsplash.com/photo-1499750310107-5fef28a66643?q=80&w=2070&auto=format&fit=crop'

export default function AboutSection3() {
  const heroRef = useRef(null)

  const revealVariants = {
    visible: (i) => ({ y: 0, opacity: 1, filter: 'blur(0px)', transition: { delay: i * 0.4, duration: 0.5 } }),
    hidden: { filter: 'blur(10px)', y: -20, opacity: 0 },
  }
  const scaleVariants = {
    visible: (i) => ({ opacity: 1, filter: 'blur(0px)', transition: { delay: i * 0.4, duration: 0.5 } }),
    hidden: { filter: 'blur(10px)', opacity: 0 },
  }

  const socials = [
    { label: 'Facebook', href: 'https://www.facebook.com/', Icon: Facebook, num: 0 },
    { label: 'Instagram', href: 'https://www.instagram.com/', Icon: Instagram, num: 1 },
    { label: 'LinkedIn', href: 'https://www.linkedin.com/', Icon: Linkedin, num: 2 },
    { label: 'YouTube', href: 'https://www.youtube.com/', Icon: Youtube, num: 3 },
  ]

  return (
    <section className="t-bg px-4 py-8" ref={heroRef}>
      <div className="mx-auto max-w-6xl">
        <div className="relative">
          <div className="absolute z-10 mb-8 flex w-[85%] items-center justify-between lg:top-4 md:top-0 sm:-top-2 -top-3">
            <div className="flex items-center gap-2 text-xl">
              <span aria-hidden="true">✱</span>
              <TimelineContent as="span" animationNum={0} timelineRef={heroRef} customVariants={revealVariants} className="text-sm font-medium">
                WHO I AM
              </TimelineContent>
            </div>
            <div className="flex gap-4">
              {socials.map(({ label, href, Icon, num }) => (
                <TimelineContent
                  key={label}
                  as="a"
                  animationNum={num}
                  timelineRef={heroRef}
                  customVariants={revealVariants}
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={label}
                  className="t-btn-outline flex h-5 w-5 items-center justify-center rounded-lg sm:h-6 sm:w-6 md:h-8 md:w-8"
                >
                  <Icon className="h-4 w-4" />
                </TimelineContent>
              ))}
            </div>
          </div>

          <TimelineContent as="figure" animationNum={4} timelineRef={heroRef} customVariants={scaleVariants} className="relative">
            <svg className="w-full" width="100%" height="100%" viewBox="0 0 100 40">
              <defs>
                <clipPath id="clip-inverted" clipPathUnits="objectBoundingBox">
                  <path
                    d="M0.0998072 1H0.422076H0.749756C0.767072 1 0.774207 0.961783 0.77561 0.942675V0.807325C0.777053 0.743631 0.791844 0.731953 0.799059 0.734076H0.969813C0.996268 0.730255 1.00088 0.693206 0.999875 0.675159V0.0700637C0.999875 0.0254777 0.985045 0.00477707 0.977629 0H0.902473C0.854975 0 0.890448 0.138535 0.850165 0.138535H0.0204424C0.00408849 0.142357 0 0.180467 0 0.199045V0.410828C0 0.449045 0.0136283 0.46603 0.0204424 0.469745H0.0523086C0.0696245 0.471019 0.0735527 0.497877 0.0733523 0.511146V0.915605C0.0723903 0.983121 0.090588 1 0.0998072 1Z"
                    fill="#D9D9D9"
                  />
                </clipPath>
              </defs>
              <image clipPath="url(#clip-inverted)" preserveAspectRatio="xMidYMid slice" width="100%" height="100%" href={HERO_IMAGE} />
            </svg>
          </TimelineContent>

          <div className="flex flex-wrap items-center justify-between py-3 text-sm">
            <TimelineContent as="div" animationNum={5} timelineRef={heroRef} customVariants={revealVariants} className="flex gap-4">
              <div className="mb-2 flex items-center gap-2 text-xs sm:text-base">
                <span className="font-bold">10+</span>
                <span className="t-muted">years of experience</span>
                <span className="t-faint">|</span>
              </div>
              <div className="mb-2 flex items-center gap-2 text-xs sm:text-base">
                <span className="font-bold">3 million</span>
                <span className="t-muted">words</span>
              </div>
            </TimelineContent>
            <div className="bottom-16 right-0 flex flex-row-reverse gap-4 lg:absolute lg:flex-col lg:gap-0">
              <TimelineContent as="div" animationNum={6} timelineRef={heroRef} customVariants={revealVariants} className="mb-2 flex items-center gap-2 text-2xl sm:text-3xl lg:text-4xl">
                <span className="font-semibold">100+</span>
                <span className="t-muted uppercase">brands</span>
              </TimelineContent>
              <TimelineContent as="div" animationNum={7} timelineRef={heroRef} customVariants={revealVariants} className="mb-2 flex items-center gap-2 text-xs sm:text-base">
                <span className="font-bold">30%</span>
                <span className="t-muted">higher engagement</span>
                <span className="t-faint lg:hidden">|</span>
              </TimelineContent>
            </div>
          </div>
        </div>

        <div className="grid gap-8 md:grid-cols-3">
          <div className="md:col-span-2">
            <h1 className="mb-8 text-2xl font-semibold !leading-[110%] sm:text-4xl md:text-5xl">
              <VerticalCutReveal splitBy="words" staggerDuration={0.1} staggerFrom="first" reverse={true} transition={{ type: 'spring', stiffness: 250, damping: 30, delay: 3 }}>
                Crafting Words That Make a Difference.
              </VerticalCutReveal>
            </h1>
            <TimelineContent as="div" animationNum={9} timelineRef={heroRef} customVariants={revealVariants} className="grid gap-8 md:grid-cols-2">
              <TimelineContent as="div" animationNum={10} timelineRef={heroRef} customVariants={revealVariants} className="text-xs sm:text-base">
                <p className="t-muted text-justify leading-relaxed">
                  My journey began as a passionate writer and evolved into a strategic copywriting career. I specialize
                  in transforming ideas into compelling content that helps brands grow.
                </p>
              </TimelineContent>
              <TimelineContent as="div" animationNum={11} timelineRef={heroRef} customVariants={revealVariants} className="text-xs sm:text-base">
                <p className="t-muted text-justify leading-relaxed">
                  Every brand has a story, and I specialize in telling yours with clarity and impact. By blending
                  creativity with strategy, I write content that resonates with audiences.
                </p>
              </TimelineContent>
            </TimelineContent>
          </div>

          <div className="md:col-span-1">
            <div className="text-right">
              <TimelineContent as="div" animationNum={12} timelineRef={heroRef} customVariants={revealVariants} className="mb-2 text-2xl font-bold">
                SANGVI
              </TimelineContent>
              <TimelineContent as="div" animationNum={13} timelineRef={heroRef} customVariants={revealVariants} className="t-muted mb-8 text-sm">
                Copywriter | Content Strategist
              </TimelineContent>
              <TimelineContent as="div" animationNum={14} timelineRef={heroRef} customVariants={revealVariants} className="mb-6">
                <p className="mb-4 font-medium">Ready to transform your brand&apos;s message into results?</p>
              </TimelineContent>
              <TimelineContent as="button" animationNum={15} timelineRef={heroRef} customVariants={revealVariants} className="t-btn-primary ml-auto flex w-fit cursor-pointer gap-2 px-5 py-3 rounded-lg font-semibold">
                LET&apos;S COLLABORATE <ArrowRight />
              </TimelineContent>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
