export function cn(...inputs) {
  return inputs
    .flatMap((input) => {
      if (!input) return []
      if (typeof input === 'string') return [input]
      if (Array.isArray(input)) return [cn(...input)]
      if (typeof input === 'object') {
        return Object.entries(input)
          .filter(([, v]) => Boolean(v))
          .map(([k]) => k)
      }
      return []
    })
    .join(' ')
}
