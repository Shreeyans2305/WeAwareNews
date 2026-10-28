export const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || 'https://weaware-api-777322408950.us-central1.run.app'
).replace(/\/$/, '')

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

export function fetchArticleAudio(id, signal) {
  return request(`/api/v1/articles/${encodeURIComponent(id)}/audio`, signal)
}

export async function requestArticleAudio(id, signal) {
  const response = await fetch(`${API_BASE}/api/v1/articles/${encodeURIComponent(id)}/audio`, {
    method: 'POST', signal,
  })
  if (!response.ok) {
    const message = await response.text().catch(() => '')
    throw new Error(`Audio request returned ${response.status}${message ? `: ${message}` : ''}`)
  }
  return response.json()
}

export function fetchPodcastEpisodes(signal) {
  return request('/api/v1/podcasts/episodes', signal)
}

async function editorialRequest(path, token, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  })
  if (!response.ok) {
    const message = await response.text().catch(() => '')
    throw new Error(`Editorial request returned ${response.status}${message ? `: ${message}` : ''}`)
  }
  return response.json()
}

export function fetchPodcastDrafts(token, signal) {
  return editorialRequest('/api/v1/editorial/podcasts/drafts', token, { signal })
}

export function approvePodcastDraft(id, token) {
  return editorialRequest(`/api/v1/editorial/podcasts/drafts/${encodeURIComponent(id)}/approve`, token, { method: 'POST' })
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

export async function sherlockRequest(path, token, { body, method = 'GET', signal } = {}) {
  const response = await fetch(`${API_BASE}/api/v1/sherlock${path}`, {
    method, signal,
    headers: { Authorization: `Bearer ${token}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = data.detail
    throw new Error(typeof detail === 'string' ? detail : detail?.message || 'Sherlock Mode is temporarily unavailable. Please try again.')
  }
  return data
}

export async function fetchSherlockPdf(id, token, signal) {
  const response = await fetch(`${API_BASE}/api/v1/sherlock/requests/${encodeURIComponent(id)}/report.pdf`, {
    signal, headers: { Authorization: `Bearer ${token}` }, cache: 'no-store',
  })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(typeof data.detail === 'string' ? data.detail : data.detail?.message || 'The PDF could not be downloaded. Please try again.')
  }
  if (!response.headers.get('Content-Type')?.includes('application/pdf')) throw new Error('The PDF is not available yet.')
  return response.blob()
}
