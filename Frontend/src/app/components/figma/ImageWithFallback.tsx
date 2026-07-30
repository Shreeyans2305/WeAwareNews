import React, { useState, useEffect } from 'react'

export function ImageWithFallback(props: React.ImgHTMLAttributes<HTMLImageElement>) {
  const [didError, setDidError] = useState(false)

  // Reset error state when src changes
  useEffect(() => {
    setDidError(false)
  }, [props.src])

  const handleError = () => {
    setDidError(true)
  }

  const { src, alt, style, className, ...rest } = props

  if (didError) {
    // Extract size and layout classes (e.g. w-full, h-full, aspect-ratio, min-h-*) to keep fallback shape intact
    const classes = className ?? ''
    const sizeClasses = classes
      .split(' ')
      .filter((c) => 
        c.startsWith('w-') || 
        c.startsWith('h-') || 
        c.startsWith('min-') || 
        c.startsWith('max-') || 
        c.startsWith('aspect-')
      )
      .join(' ')

    return (
      <div
        className={`relative flex flex-col items-center justify-center bg-[#D6D3CD] text-[#5c5a54] border border-[#030213]/10 overflow-hidden font-mono text-[9px] tracking-wider select-none p-2 ${sizeClasses}`}
        style={{
          ...style,
          minHeight: style?.height || style?.minHeight || '100px', // Fallback height to prevent layout collapse
        }}
      >
        {/* Subtle halftone background pattern */}
        <div 
          className="absolute inset-0 pointer-events-none opacity-20 mix-blend-multiply"
          style={{
            backgroundImage: "radial-gradient(circle, #000000 20%, transparent 22%)",
            backgroundSize: "4px 4px"
          }}
        />
        
        {/* Newspaper folded seam effect */}
        <div className="absolute inset-0 border border-dashed border-[#030213]/10 pointer-events-none m-1" />

        <div className="relative z-10 flex flex-col items-center gap-1 text-center">
          <svg
            className="w-5 h-5 opacity-80 animate-pulse text-[#B22222]"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="1.8"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
          <span className="font-bold uppercase text-[8px] leading-tight text-[#030213]/85">Feed Consensus Fail</span>
          <span className="opacity-60 text-[7px] max-w-[90%] truncate">{alt || 'Image offline'}</span>
        </div>
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={alt}
      className={className}
      style={style}
      {...rest}
      onError={handleError}
    />
  )
}

