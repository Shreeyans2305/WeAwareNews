import { cn } from '../../lib/utils.js'

export function Card({ className, ...props }) {
  return (
    <div
      className={cn('t-card rounded-2xl border', className)}
      {...props}
    />
  )
}
