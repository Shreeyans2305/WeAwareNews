import { onRequest } from 'firebase-functions/v2/https'

const SITE_ORIGIN = 'https://weaware-3504c.web.app'
const API_ORIGIN = 'https://weaware-api-777322408950.us-central1.run.app'
const DEFAULT_DESCRIPTION = 'WeAware brings multiple reports together, keeping sources and uncertainty in view.'

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char])
}

function replaceMeta(html, pattern, tag) {
  return pattern.test(html) ? html.replace(pattern, tag) : html.replace('</head>', `    ${tag}\n  </head>`)
}

function pageWithArticleMetadata(html, article, url) {
  const title = article?.title || 'Story unavailable — WeAware'
  const description = article?.summary || DEFAULT_DESCRIPTION
  const image = article?.image || `${SITE_ORIGIN}/weaware-logo.png`
  const tags = [
    [/<title>.*?<\/title>/is, `<title>${escapeHtml(title)} — WeAware</title>`],
    [/<meta\s+name="description"[^>]*>/i, `<meta name="description" content="${escapeHtml(description)}" />`],
    [/<meta\s+property="og:type"[^>]*>/i, '<meta property="og:type" content="article" />'],
    [/<meta\s+property="og:site_name"[^>]*>/i, '<meta property="og:site_name" content="WeAware" />'],
    [/<meta\s+property="og:title"[^>]*>/i, `<meta property="og:title" content="${escapeHtml(title)}" />`],
    [/<meta\s+property="og:description"[^>]*>/i, `<meta property="og:description" content="${escapeHtml(description)}" />`],
    [/<meta\s+property="og:url"[^>]*>/i, `<meta property="og:url" content="${escapeHtml(url)}" />`],
    [/<meta\s+property="og:image"[^>]*>/i, `<meta property="og:image" content="${escapeHtml(image)}" />`],
    [/<meta\s+name="twitter:card"[^>]*>/i, '<meta name="twitter:card" content="summary_large_image" />'],
    [/<meta\s+name="twitter:title"[^>]*>/i, `<meta name="twitter:title" content="${escapeHtml(title)}" />`],
    [/<meta\s+name="twitter:description"[^>]*>/i, `<meta name="twitter:description" content="${escapeHtml(description)}" />`],
    [/<link\s+rel="canonical"[^>]*>/i, `<link rel="canonical" href="${escapeHtml(url)}" />`],
  ]
  return tags.reduce((result, [pattern, tag]) => replaceMeta(result, pattern, tag), html)
}

export const shareStory = onRequest({
  region: 'us-central1',
  memory: '256MiB',
  timeoutSeconds: 15,
}, async (request, response) => {
  const match = request.path.match(/^\/s\/([^/]+)\/?$/)
  if (!match) {
    response.status(404).send('Story not found')
    return
  }

  let storyId
  try {
    storyId = decodeURIComponent(match[1])
  } catch {
    response.status(400).send('Invalid story link')
    return
  }

  try {
    const [shellResponse, articleResponse] = await Promise.all([
      fetch(`${SITE_ORIGIN}/index.html`, { signal: AbortSignal.timeout(8000) }),
      fetch(`${API_ORIGIN}/api/v1/articles/${encodeURIComponent(storyId)}`, { signal: AbortSignal.timeout(8000) }).catch(() => null),
    ])
    if (!shellResponse.ok) throw new Error(`Site shell returned ${shellResponse.status}`)
    const html = await shellResponse.text()
    const article = articleResponse?.ok ? await articleResponse.json() : null
    const url = `${SITE_ORIGIN}/s/${encodeURIComponent(storyId)}`

    response.set('Cache-Control', article ? 'public, max-age=300, s-maxage=600' : 'public, max-age=60, s-maxage=60')
    response.set('X-Content-Type-Options', 'nosniff')
    response.status(200).type('html').send(pageWithArticleMetadata(html, article, url))
  } catch (error) {
    console.error('Unable to render shared story page', error)
    response.set('Cache-Control', 'no-store')
    response.status(503).send('WeAware is temporarily unable to open this story. Please try again.')
  }
})
