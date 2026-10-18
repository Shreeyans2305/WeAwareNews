const PALETTES = {
  business: ['#10243a', '#40b7a8', '#f2c078'],
  culture: ['#351a38', '#e77973', '#f4ce84'],
  politics: ['#22233d', '#7c8fe8', '#f1ae75'],
  world: ['#102e34', '#4ebaa0', '#d7c47a'],
  science: ['#182c42', '#63b3ed', '#a6dfc4'],
  technology: ['#182c42', '#63b3ed', '#b697f3'],
  health: ['#193634', '#63c6a4', '#e6c77b'],
  environment: ['#15372e', '#75ba72', '#e4ca78'],
  default: ['#27283d', '#8d8bd8', '#edaf80'],
}

function hashText(text = '') {
  let hash = 2166136261
  for (const char of text) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619)
  return hash >>> 0
}

export default function StoryArtwork({ story, className = '' }) {
  const topic = String(story.topic || '').toLowerCase()
  const palette = PALETTES[topic] || PALETTES.default
  const hash = hashText(`${story.id || ''}${story.title || ''}`)
  const cx = 150 + (hash % 220)
  const cy = 45 + ((hash >>> 8) % 140)
  const accent = palette[1]
  const glow = palette[2]
  const id = `art-${String(story.id || hash).replace(/[^a-zA-Z0-9_-]/g, '')}`

  return (
    <svg
      viewBox="0 0 640 360"
      preserveAspectRatio="xMidYMid slice"
      role="img"
      aria-label={`Editorial illustration for ${story.title}`}
      className={`block h-full w-full ${className}`}
    >
      <defs>
        <linearGradient id={`${id}-base`} x1="0" y1="0" x2="1" y2="1">
          <stop stopColor={palette[0]} />
          <stop offset="1" stopColor="#10151d" />
        </linearGradient>
        <radialGradient id={`${id}-glow`}>
          <stop stopColor={glow} stopOpacity=".58" />
          <stop offset="1" stopColor={glow} stopOpacity="0" />
        </radialGradient>
        <pattern id={`${id}-grid`} width="32" height="32" patternUnits="userSpaceOnUse">
          <path d="M32 0H0V32" fill="none" stroke="white" strokeOpacity=".08" />
        </pattern>
        <linearGradient id={`${id}-fade`} x1="0" y1="0" x2="0" y2="1">
          <stop offset=".2" stopColor="#0c1017" stopOpacity="0" />
          <stop offset="1" stopColor="#0c1017" stopOpacity=".9" />
        </linearGradient>
      </defs>
      <rect width="640" height="360" fill={`url(#${id}-base)`} />
      <rect width="640" height="360" fill={`url(#${id}-grid)`} />
      <ellipse cx={cx} cy={cy} rx="230" ry="190" fill={`url(#${id}-glow)`} />
      <circle cx={cx} cy={cy} r={62 + (hash % 42)} fill="none" stroke={accent} strokeOpacity=".65" strokeWidth="1.5" />
      <circle cx={cx} cy={cy} r={100 + (hash % 30)} fill="none" stroke={glow} strokeOpacity=".32" />
      <path d={`M${cx - 170} 280 Q${cx - 35} ${90 + (hash % 90)} ${cx + 190} 70`} fill="none" stroke={accent} strokeOpacity=".48" strokeWidth="2" />
      <path d={`M${cx - 150} 315 Q${cx + 20} ${185 + (hash % 50)} ${cx + 220} 205`} fill="none" stroke={glow} strokeOpacity=".4" strokeWidth="1" />
      {[0, 1, 2, 3, 4].map((i) => {
        const x = 65 + ((hash >>> (i * 3)) % 500)
        const y = 50 + ((hash >>> (i * 5 + 2)) % 240)
        return <circle key={i} cx={x} cy={y} r={i === 0 ? 4 : 2} fill={i % 2 ? accent : glow} opacity=".8" />
      })}
      <rect y="230" width="640" height="130" fill={`url(#${id}-fade)`} />
      <text x="34" y="300" fill="white" fillOpacity=".72" fontSize="12" fontFamily="sans-serif" fontWeight="700" letterSpacing="2.4">
        {String(story.topic || 'WEAWARE').toUpperCase()} · EDITORIAL ARTWORK
      </text>
      <text x="34" y="332" fill="white" fontSize="17" fontFamily="Georgia, serif" fontWeight="700">
        {String(story.title || '').slice(0, 58)}{String(story.title || '').length > 58 ? '…' : ''}
      </text>
    </svg>
  )
}
