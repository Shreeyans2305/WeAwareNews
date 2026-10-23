import { useRef, useState } from 'react'
import { CheckCircle2, Copy, Link2, Mail, MessageCircle, Send, Share2, X } from 'lucide-react'
import { useDialogFocus } from '../lib/useDialogFocus.js'

export default function ShareSheet({ story, open, onClose }) {
  const [copied, setCopied] = useState(false)
  const [sent, setSent] = useState(false)
  const [friend, setFriend] = useState('')
  const dialogRef = useRef(null)

  useDialogFocus(dialogRef, onClose, open && Boolean(story), 'button[aria-label="Close"]')

  if (!open || !story) return null

  const url = `https://weaware.news/s/${story.id}`
  const text = `${story.title} — ${story.consensus}% consensus, sources shown`

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(url)
    } catch {
      const ta = document.createElement('textarea')
      ta.value = url
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    setCopied(true)
    window.setTimeout(() => setCopied(false), 2000)
  }

  const nativeShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({ title: story.title, text, url })
      } catch {
        // user dismissed — no-op
      }
    } else {
      copyLink()
    }
  }

  const sendToFriend = (e) => {
    e.preventDefault()
    if (!friend.trim()) return
    setSent(true)
    window.setTimeout(() => {
      setSent(false)
      setFriend('')
    }, 2500)
  }

  return (
    <div ref={dialogRef} className="fixed inset-0 z-50 flex items-end justify-center sm:items-center" role="dialog" aria-modal="true" aria-label={`Share ${story.title}`} tabIndex={-1}>
      <button type="button" aria-label="Close share dialog" tabIndex={-1} onClick={onClose} className="absolute inset-0 bg-black/60" style={{ background: 'rgba(0,0,0,0.6)' }} />
      <div className="page-enter t-card relative w-full max-w-md overflow-hidden rounded-t-2xl border sm:rounded-2xl">
        <div className="t-border flex items-center gap-2.5 border-b px-5 py-4">
          <Share2 className="h-4 w-4" />
          <h2 className="font-display text-lg font-bold">Share this cross-check</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="t-btn-outline ml-auto rounded-full p-1.5">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-5 py-4">
          <p className="line-clamp-2 text-sm">{story.title}</p>
          <p className="t-muted mt-1 flex items-center gap-1.5 text-xs">
            <Link2 className="h-3.5 w-3.5" />
            <span className="truncate">{url}</span>
          </p>

          <div className="mt-4 grid grid-cols-4 gap-2">
            <button type="button" onClick={copyLink} className="t-btn-outline flex flex-col items-center gap-1.5 rounded-xl px-2 py-3 text-[11px]">
              {copied ? <CheckCircle2 className="h-5 w-5" /> : <Copy className="h-5 w-5" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
            <a href={`https://wa.me/?text=${encodeURIComponent(`${text} ${url}`)}`} target="_blank" rel="noreferrer" className="t-btn-outline flex flex-col items-center gap-1.5 rounded-xl px-2 py-3 text-[11px]">
              <MessageCircle className="h-5 w-5" />
              WhatsApp
            </a>
            <a href={`https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`} target="_blank" rel="noreferrer" className="t-btn-outline flex flex-col items-center gap-1.5 rounded-xl px-2 py-3 text-[11px]">
              <Send className="h-5 w-5" />
              Post
            </a>
            <a href={`mailto:?subject=${encodeURIComponent(story.title)}&body=${encodeURIComponent(`${text}\n\n${url}`)}`} className="t-btn-outline flex flex-col items-center gap-1.5 rounded-xl px-2 py-3 text-[11px]">
              <Mail className="h-5 w-5" />
              Email
            </a>
          </div>

          {navigator.share ? (
            <button type="button" onClick={nativeShare} className="t-btn-primary mt-2 w-full rounded-full px-5 py-2.5 text-sm font-medium">
              System share…
            </button>
          ) : null}

          <form onSubmit={sendToFriend} className="t-card t-border mt-4 rounded-xl border p-3">
            <label htmlFor="share-friend" className="t-muted text-xs font-medium">Send to a friend on WeAware (mock)</label>
            <div className="mt-2 flex gap-2">
              <input
                id="share-friend"
                value={friend}
                onChange={(e) => setFriend(e.target.value)}
                placeholder="username or email"
                className="t-field t-border w-full min-w-0 flex-1 rounded-full border px-4 py-2 text-sm outline-none"
              />
              <button type="submit" className="t-btn-outline shrink-0 rounded-full px-4 py-2 text-sm font-medium">Send</button>
            </div>
            {sent ? (
              <p role="status" className="mt-2 flex items-center gap-1.5 text-xs">
                <CheckCircle2 className="h-3.5 w-3.5" />
                Sent to activity feed (frontend mock, no backend yet).
              </p>
            ) : (
              <p className="t-faint mt-2 text-[11px]">Frontend only — wire to Stream Feeds when backend lands.</p>
            )}
          </form>
        </div>
      </div>
    </div>
  )
}
