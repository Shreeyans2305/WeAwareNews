export const SITE_ORIGIN = 'https://weaware-3504c.web.app'

export function storyShareUrl(id) {
  return `${SITE_ORIGIN}${storySharePath(id)}`
}

export function storySharePath(id) {
  return `/s/${encodeURIComponent(id)}`
}

export function storyIdFromPath(pathname) {
  const match = pathname.match(/^\/s\/([^/]+)\/?$/)
  if (!match) return null
  try {
    return decodeURIComponent(match[1])
  } catch {
    return null
  }
}
