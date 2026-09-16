import { useState } from 'react'
import { CheckCircle2, Copy, Link2, Mail, MessageCircle, Send, Share2, X } from 'lucide-react'

const ACCENT = '#00F0FF'

export default function ShareSheet({ story, open, onClose }) {
  const [copied, setCopied] = useState(false)
  const [sent, setSent] = useState(false)
  const [friend, setFriend] = useState('')

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
        // user dismissed — no-op (frontend mock)
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
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center" role="dialog" aria-modal="true" aria-label={`Share ${story.title}`}>
      <button type="button" aria-label="Close share dialog" onClick={onClose} className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div className="page-enter relative w-full max-w-md overflow-hidden rounded-t-2xl border border-white/15 bg-[#111] sm:rounded-2xl">
        <div className="flex items-center gap-2.5 border-b border-white/10 px-5 py-4">
          <Share2 className="h-4 w-4" style={{ color: ACCENT }} />
          <h2 className="font-display text-lg font-bold text-white">Share this cross-check</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="ml-auto rounded-full p-1.5 text-white/60 hover:bg-white/10 hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-5 py-4">
          <p className="line-clamp-2 text-sm text-white/70">{story.title}</p>
          <p className="mt-1 flex items-center gap-1.5 text-xs text-white/45">
            <Link2 className="h-3.5 w-3.5" />
            <span className="truncate">{url}</span>
          </p>

          <div className="mt-4 grid grid-cols-4 gap-2">
            <button
              type="button"
              onClick={copyLink}
              className="flex flex-col items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.04] px-2 py-3 text-[11px] text-white/70 hover:bg-white/10 hover:text-white"
            >
              {copied ? <CheckCircle2 className="h-5 w-5" style={{ color: ACCENT }} /> : <Copy className="h-5 w-5" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
            <a
              href={`https://wa.me/?text=${encodeURIComponent(`${text} ${url}`)}`}
              target="_blank"
              rel="noreferrer"
              className="flex flex-col items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.04] px-2 py-3 text-[11px] text-white/70 hover:bg-white/10 hover:text-white"
            >
              <MessageCircle className="h-5 w-5" />
              WhatsApp
            </a>
            <a
              href={`https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`}
              target="_blank"
              rel="noreferrer"
              className="flex flex-col items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.04] px-2 py-3 text-[11px] text-white/70 hover:bg-white/10 hover:text-white"
            >
              <Send className="h-5 w-5" />
              Post
            </a>
            <a
              href={`mailto:?subject=${encodeURIComponent(story.title)}&body=${encodeURIComponent(`${text}\n\n${url}`)}`}
              className="flex flex-col items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.04] px-2 py-3 text-[11px] text-white/70 hover:bg-white/10 hover:text-white"
            >
              <Mail className="h-5 w-5" />
              Email
            </a>
          </div>

          {navigator.share ? (
            <button
              type="button"
              onClick={nativeShare}
              className="mt-2 w-full rounded-full bg-white px-5 py-2.5 text-sm font-medium text-black hover:bg-white/85"
            >
              System share…
            </button>
          ) : null}

          <form onSubmit={sendToFriend} className="mt-4 rounded-xl border border-white/10 bg-black/40 p-3">
            <label htmlFor="share-friend" className="text-xs font-medium text-white/60">
              Send to a friend on WeAware <span className="text-white/35">(Stream API • mock)</span>
            </label>
            <div className="mt-2 flex gap-2">
              <input
                id="share-friend"
                value={friend}
                onChange={(e) => setFriend(e.target.value)}
                placeholder="username or email"
                className="w-full min-w-0 flex-1 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-white outline-none placeholder-white/30 focus:border-white/30"
              />
              <button
                type="submit"
                className="shrink-0 rounded-full border px-4 py-2 text-sm font-medium text-white hover:bg-white/10"
                style={{ borderColor: `${ACCENT}4D` }}
              >
                Send
              </button>
            </div>
            {sent ? (
              <p role="status" className="mt-2 flex items-center gap-1.5 text-xs" style={{ color: ACCENT }}>
                <CheckCircle2 className="h-3.5 w-3.5" />
                Sent to activity feed (frontend mock, no backend yet).
              </p>
            ) : (
              <p className="mt-2 text-[11px] text-white/35">Frontend only — wire to Stream Feeds when backend lands.</p>
            )}
          </form>
        </div>
      </div>
    </div>
  )
}
