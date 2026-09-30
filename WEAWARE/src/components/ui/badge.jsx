import { cn } from '../../lib/utils.js'

export function Badge({ className, variant = 'default', ...props }) {
  const variants = {
    default: 't-btn-primary border-transparent',
    outline: 't-btn-outline bg-transparent',
  }
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium',
        variants[variant],
        className,
      )}
      {...props}
    />
  )
}
