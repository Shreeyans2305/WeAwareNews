import { cloneElement, forwardRef, isValidElement } from 'react'
import { cn } from '../../lib/utils.js'

const variantClasses = {
  default: 't-btn-primary border-transparent',
  outline: 't-btn-outline bg-transparent',
  ghost: 'border border-transparent bg-transparent t-muted hover:t-fg',
}

const sizeClasses = {
  default: 'h-10 px-5 py-2 text-sm',
  sm: 'h-9 px-4 text-xs',
  lg: 'h-12 px-8 text-base',
  icon: 'h-10 w-10 p-0',
}

export const Button = forwardRef(function Button(
  { className, variant = 'default', size = 'default', asChild = false, ...props },
  ref,
) {
  const classes = cn(
    'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full font-medium transition-colors focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50',
    variantClasses[variant],
    sizeClasses[size],
    className,
  )

  if (asChild && isValidElement(props.children)) {
    return cloneElement(props.children, {
      className: cn(classes, props.children.props.className),
      ref,
      ...props,
    })
  }

  return <button ref={ref} className={classes} {...props} />
})
