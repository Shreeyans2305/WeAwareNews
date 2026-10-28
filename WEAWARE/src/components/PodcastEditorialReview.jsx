import { useEffect, useState } from 'react'
import { Check, ChevronDown, FileText, LockKeyhole, RefreshCw } from 'lucide-react'
import { useAuth } from '../auth/AuthContext.jsx'
import { approvePodcastDraft, fetchPodcastDrafts, fetchPodcastEpisodes } from '../lib/api.js'

const wait = (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds))

export default function PodcastEditorialReview({ onPublished }) {
  const { user, requestSignIn } = useAuth()
  const [drafts, setDrafts] = useState([])
  const [loading, setLoading] = useState(false)
  const [approvingId, setApprovingId] = useState(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const loadDrafts = async () => {
    if (!user) return
    setLoading(true)
    setError('')
    try {
      const token = await user.getIdToken()
      const result = await fetchPodcastDrafts(token)
      setDrafts(result.drafts || [])
    } catch (reason) {
      if (reason.message.includes('returned 403')) {
        setError('This signed-in account does not have podcast editorial access.')
      } else if (reason.message.includes('returned 401')) {
        setError('We could not verify this Firebase session. Sign out, sign back in, and retry.')
      } else {
        setError('Could not load podcast drafts. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setDrafts([])
    setMessage('')
    setError('')
    if (user) loadDrafts()
  }, [user])

  const approve = async (draft) => {
    setApprovingId(draft.id)
    setError('')
    setMessage('Approval accepted. Audio is being generated…')
    try {
      const token = await user.getIdToken()
      await approvePodcastDraft(draft.id, token)
      setDrafts((current) => current.filter((item) => item.id !== draft.id))
      // The task publishes the episode after its MP3 is ready. Poll briefly so
      // it can appear in the public listening desk without a page reload.
      for (let attempt = 0; attempt < 12; attempt += 1) {
        await wait(5000)
        const result = await fetchPodcastEpisodes()
        const episodes = result.episodes || []
        if (episodes.some((episode) => episode.id === draft.id)) {
          onPublished(episodes, draft.id)
          setMessage('Episode published and ready to listen.')
          return
        }
      }
      setMessage('Audio is still processing. The episode will appear in the listening desk when it is ready; refresh the page to check.')
    } catch (reason) {
      setMessage('')
      if (reason.message.includes('returned 403')) {
        setError('This signed-in account does not have podcast editorial access.')
      } else if (reason.message.includes('returned 404')) {
        setError('This draft is no longer available. Refresh the draft list.')
      } else {
        setError('Approval failed. Please try again.')
      }
    } finally {
      setApprovingId(null)
    }
  }

  return (
    <details className="t-card t-border mt-8 border">
      <summary className="flex cursor-pointer list-none items-center gap-3 px-5 py-4 [&::-webkit-details-marker]:hidden">
        <LockKeyhole className="h-4 w-4" aria-hidden="true" />
        <span className="flex-1">
          <span className="block text-sm font-semibold">Editorial review</span>
          <span className="t-muted mt-0.5 block text-xs">Review scripts and sources before an episode is published.</span>
        </span>
        <ChevronDown className="h-4 w-4" aria-hidden="true" />
      </summary>

      <div className="t-border border-t px-5 py-5">
        {!user ? (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="t-muted text-sm">Sign in with an authorized editor account to review drafts.</p>
            <button type="button" onClick={requestSignIn} className="t-btn-outline px-4 py-2 text-sm">Sign in</button>
          </div>
        ) : (
          <>
            <div className="mb-4 flex items-center justify-between gap-3">
              <p className="t-muted text-sm">Signed in as {user.email || 'editor'}</p>
              <button type="button" onClick={loadDrafts} disabled={loading || !!approvingId} className="t-btn-outline flex items-center gap-2 px-3 py-2 text-xs disabled:opacity-50">
                <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />
                Refresh drafts
              </button>
            </div>

            {error && <p role="alert" className="mb-4 rounded-lg border border-red-400/40 px-4 py-3 text-sm">{error}</p>}
            {message && <p role="status" className="mb-4 rounded-lg border px-4 py-3 text-sm">{message}</p>}
            {loading ? <p className="t-muted py-3 text-sm">Loading drafts…</p>
              : !error && drafts.length === 0 ? <p className="t-muted py-3 text-sm">There are no drafts awaiting review.</p>
                : drafts.map((draft) => (
                  <article key={draft.id} className="t-border border p-4 md:p-5">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div>
                        <p className="kicker">{draft.topic} · Draft for review</p>
                        <h3 className="headline-serif mt-2 text-2xl">{draft.title}</h3>
                        <p className="t-muted mt-2 max-w-3xl text-sm leading-relaxed">{draft.description}</p>
                      </div>
                      <span className="t-faint flex items-center gap-1.5 text-xs"><FileText className="h-3.5 w-3.5" aria-hidden="true" />{draft.script.trim().split(/\s+/).length} words</span>
                    </div>

                    <details className="t-border mt-5 border-t pt-4">
                      <summary className="flex cursor-pointer items-center gap-2 text-sm font-medium">
                        <FileText className="h-4 w-4" aria-hidden="true" /> Preview script and sources
                      </summary>
                      <div className="t-muted mt-4 whitespace-pre-wrap font-body-serif text-sm leading-7">{draft.script}</div>
                      <div className="mt-5">
                        <h4 className="kicker">Source links</h4>
                        <ul className="mt-2 list-inside list-disc space-y-1.5 text-sm">
                          {(draft.sourceUrls || []).map((url) => (
                            <li key={url}><a className="underline underline-offset-4" href={url} target="_blank" rel="noreferrer">{url}</a></li>
                          ))}
                        </ul>
                      </div>
                    </details>

                    <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
                      <p className="t-faint max-w-2xl text-xs">Approving queues AI narration. The episode becomes public after audio generation finishes.</p>
                      <button type="button" onClick={() => approve(draft)} disabled={!!approvingId} className="t-btn-primary flex items-center gap-2 px-4 py-2.5 text-sm font-medium disabled:opacity-50">
                        {approvingId === draft.id ? <RefreshCw className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Check className="h-4 w-4" aria-hidden="true" />}
                        Approve and publish
                      </button>
                    </div>
                  </article>
                ))}
          </>
        )}
      </div>
    </details>
  )
}
