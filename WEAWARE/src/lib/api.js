const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

async function request(path, signal) {
  const response = await fetch(`${API_BASE}${path}`, { signal })
  if (!response.ok) {
    const message = await response.text().catch(() => '')
    throw new Error(`News API returned ${response.status}${message ? `: ${message}` : ''}`)
  }
  return response.json()
}

export function fetchArticles({ topic = 'All', query = '', limit = 24, offset = 0, signal } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (topic && topic !== 'All') params.set('topic', topic)
  if (query.trim()) params.set('q', query.trim())
  return request(`/api/v1/articles?${params}`, signal)
}

export function fetchArticle(id, signal) {
  return request(`/api/v1/articles/${encodeURIComponent(id)}`, signal)
}

export function fetchTopics(signal) {
  return request('/api/v1/topics', signal)
}

export function prioritizeStoriesWithImages(stories) {
  // Array#sort is stable, so publication order is preserved within each group.
  return [...stories].sort((a, b) => Number(Boolean(b.image)) - Number(Boolean(a.image)))
}

export function toStory(article) {
  return {
    ...article,
    body: Array.isArray(article.body) ? article.body : [],
    sources: Array.isArray(article.sources) ? article.sources : [],
    flaggedClaims: Array.isArray(article.flaggedClaims) ? article.flaggedClaims : [],
    // Keep missing images explicit so the UI can render article-specific artwork
    // instead of repeating the same demo poster across unrelated stories.
    image: article.image || null,
    publishedAt: article.publishedAt
      ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(article.publishedAt))
      : 'Recently published',
  }
}
