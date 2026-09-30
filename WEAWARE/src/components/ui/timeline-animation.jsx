import { forwardRef } from 'react'
import { motion } from 'framer-motion'

/**
 * TimelineContent — minimal Vite/JSX port of the timeline-animation primitive.
 *
 * Original API (from 21st.dev / shadcn-style `timeline-animation`):
 *   <TimelineContent as="div" animationNum={0} timelineRef={ref} customVariants={variants} />
 *
 * This port keeps the same props contract but uses `whileInView` sequencing
 * instead of a full scroll-timeline provider, so it works without extra context.
 * `customVariants` must define `hidden` and `visible(i)` where `i` = animationNum.
 */
const TimelineContent = forwardRef(function TimelineContent(
  {
    as = 'div',
    animationNum = 0,
    timelineRef: _timelineRef,
    customVariants,
    children,
    ...rest
  },
  fwdRef,
) {
  const MotionTag = motion[as] ?? motion.div

  const fallbackVariants = {
    hidden: { y: -20, opacity: 0, filter: 'blur(10px)' },
    visible: (i = 0) => ({
      y: 0,
      opacity: 1,
      filter: 'blur(0px)',
      transition: { delay: i * 0.08, duration: 0.5 },
    }),
  }

  return (
    <MotionTag
      ref={fwdRef}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, amount: 0.2 }}
      custom={animationNum}
      variants={customVariants ?? fallbackVariants}
      {...rest}
    >
      {children}
    </MotionTag>
  )
})

export { TimelineContent }
export default TimelineContent
