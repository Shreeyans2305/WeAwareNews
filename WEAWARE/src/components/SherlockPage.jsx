import { useEffect, useRef, useState } from 'react'
import { Search, ArrowUpRight, Clock3, BookOpen, ShieldCheck, RefreshCw, Download } from 'lucide-react'
import { useAuth } from '../auth/AuthContext.jsx'
import { sherlockRequest, fetchSherlockPdf } from '../lib/api.js'
import './sherlock.css'

const LENGTHS = { brief: { label: 'Brief', words: '400–700', time: '2–4 min' }, standard: { label: 'Standard', words: '800–1,500', time: '4–7 min' }, detailed: { label: 'Detailed', words: '1,500–2,400', time: '7–11 min' } }

const ACTIVE = new Set(['queued', 'researching', 'awaiting_review'])
const STATUS = { queued: 'On Jeff’s desk', researching: 'Following the evidence', awaiting_review: 'With the editor', completed: 'Ready to read', failed: 'Unable to complete', cancelled: 'Cancelled', insufficient_evidence: 'Evidence too limited' }
const STAGES = { discovery: 'Preparing the research', planning: 'Defining the investigation', evidence: 'Cross-checking source material', drafting: 'Writing the brief', verification: 'Verifying claims and citations' }
const FAILURES = {
  insufficient_evidence: 'Jeff could not find enough accessible, independent evidence for a thorough report.',
  budget_exhausted: 'The investigation reached a pilot spending limit before it could pass verification.',
  verification_failed: 'The draft did not pass the source verification check.',
  quality_gate: 'The investigation did not meet the pilot’s evidence and depth requirements.',
  scope_not_supported: 'This question needs a narrower scope or falls outside supported public-information research.',
  editor_rejected: 'The editor found issues that prevented delivery of this report.',
  worker_expired: 'The investigation could not finish within its processing window.',
}

function ResearchReport({ investigation, onDownload, downloading }) {
  const report = investigation.report
  const wordCount = report.wordCount ?? report.sections.reduce((total, section) => total + section.paragraphs.reduce((n, paragraph) => n + paragraph.text.trim().split(/\s+/).length, 0), 0)
  const sources = Object.fromEntries(report.sources.map(source => [source.id, source]))
  const claims = Object.fromEntries(report.claims.map(claim => [claim.id, claim]))
  return <article className="jeff-report" aria-labelledby="report-title">
    <div className="jeff-panel-heading"><p className="jeff-eyebrow">The research brief · Journalist Jeff</p><button type="button" className="t-btn-outline jeff-pdf-button" disabled={downloading} onClick={onDownload}><Download size={15} aria-hidden="true" />{downloading ? 'Preparing PDF…' : 'Download PDF'}</button></div>
    <h2 id="report-title">{report.title}</h2>
    <p className="jeff-answer">{report.answer}</p>
    <p className="jeff-meta">Research cutoff: {new Date(report.cutoff).toLocaleString()} · Editor reviewed<br />{LENGTHS[investigation.reportLength || report.reportLength || 'standard'].label} · {wordCount.toLocaleString()} words of analysis · About {Math.max(1, Math.ceil(wordCount / 220))} min read</p>
    {report.sections.map((section, index) => <section key={index} className="jeff-report-section">
      <h3>{section.heading}</h3>
      {section.paragraphs.map((paragraph, i) => <div key={i}>
        <p>{paragraph.text}</p>
        <details className="jeff-evidence"><summary>Inspect the evidence · {paragraph.claimIds.length} cited findings</summary>
          {paragraph.claimIds.map(id => <div key={id} className="jeff-claim">
            <p><strong>{claims[id]?.finding}</strong> <span className="jeff-meta">{claims[id]?.state}</span></p>
            {claims[id]?.caveat && <p>{claims[id].caveat}</p>}
            {claims[id]?.evidence.map((item, n) => <blockquote key={n}>
              <p>“{item.quote}”</p>
              <a href={sources[item.sourceId]?.url} target="_blank" rel="noopener noreferrer">{sources[item.sourceId]?.title} <ArrowUpRight size={12} aria-hidden="true" /></a>
            </blockquote>)}
          </div>)}
        </details>
      </div>)}
    </section>)}
    <section className="jeff-report-section"><h3>What remains unknown</h3><ul>{report.unknowns.map((item, i) => <li key={i}>{item}</li>)}</ul></section>
    <section className="jeff-report-section"><h3>Research limitations</h3><ul>{report.limitations.map((item, i) => <li key={i}>{item}</li>)}</ul><p className="jeff-meta">{report.retrievalGaps} candidate sources were unavailable or duplicates. Accessible web text only; private records and inaccessible documents were excluded.</p></section>
    <section className="jeff-report-section"><h3>The source notebook</h3>
      <ol>{report.sources.map(source => <li key={source.id}><a href={source.url} target="_blank" rel="noopener noreferrer">{source.title} ↗</a><span className="jeff-meta"> {source.publisherHost} · Publication date: {source.publishedAt || 'not available'}</span></li>)}</ol>
    </section>
    {report.searchDiscovery?.length > 0 && <section className="jeff-report-section"><h3>Google Search discovery</h3><p className="jeff-meta">These Google-grounded discovery results helped locate sources. Jeff’s analysis above was checked separately against retrieved documents.</p>
      {report.searchDiscovery.map((search, index) => <div key={index} className="jeff-discovery">
        <h4>{search.query}</h4>
        {search.renderedContent && <iframe title={`Google Search suggestions ${index+1}`} srcDoc={search.renderedContent} sandbox="allow-popups allow-popups-to-escape-sandbox" referrerPolicy="no-referrer" className="jeff-google-suggestions" />}
        <details><summary>Discovery results and sources</summary><p>{search.text}</p><ul>{search.sources.map((source,i) => <li key={i}><a href={source.url} target="_blank" rel="noopener noreferrer">{source.title || 'Source'}</a></li>)}</ul></details>
      </div>)}
    </section>}
    <p className="jeff-disclosure">{report.disclosure}</p>
  </article>
}

export default function SherlockPage() {
  const { user, ready, requestSignIn } = useAuth()
  const [access, setAccess] = useState(null)
  const [requests, setRequests] = useState([])
  const [selected, setSelected] = useState(null)
  const [question, setQuestion] = useState('')
  const [scope, setScope] = useState('')
  const [reportLength, setReportLength] = useState('standard')
  const [downloading, setDownloading] = useState(false)
  const [consent, setConsent] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const submission = useRef(null)
  const generation = useRef(0)
  const activeRequest = requests.find(item => ACTIVE.has(item.status))

  useEffect(() => {
    const epoch = ++generation.current
    setAccess(null); setRequests([]); setSelected(null); setError(''); setLoading(Boolean(user))
    setQuestion(''); setScope(''); setReportLength('standard'); setDownloading(false); setConsent(false); setBusy(false); submission.current = null
    if (!user) return undefined
    const controller = new AbortController()
    async function load() {
      try {
        const token = await user.getIdToken()
        const [eligibility, history] = await Promise.all([
          sherlockRequest('/entitlement', token, { signal: controller.signal }),
          sherlockRequest('/requests', token, { signal: controller.signal }),
        ])
        if (generation.current !== epoch) return
        setAccess(eligibility); setRequests(history.requests); setError('')
      } catch (err) {
        if (err.name !== 'AbortError' && generation.current === epoch) setError(err.message)
      } finally {
        if (generation.current === epoch) setLoading(false)
      }
    }
    load()
    return () => { generation.current++; controller.abort() }
  }, [user])

  useEffect(() => {
    if (!user || !activeRequest) return undefined
    const epoch = generation.current
    const timer = setInterval(async () => {
      try {
        const token = await user.getIdToken()
        const [eligibility, history, detail] = await Promise.all([
          sherlockRequest('/entitlement', token), sherlockRequest('/requests', token),
          selected?.id ? sherlockRequest(`/requests/${encodeURIComponent(selected.id)}`, token) : Promise.resolve(null),
        ])
        if (generation.current !== epoch) return
        setAccess(eligibility); setRequests(history.requests)
        if (detail) setSelected(detail)
      } catch (err) { if (generation.current === epoch) setError(err.message) }
    }, 30000)
    return () => clearInterval(timer)
  }, [user, Boolean(activeRequest), selected?.id])

  async function refresh() {
    const epoch = generation.current
    const token = await user.getIdToken()
    const [eligibility, history] = await Promise.all([sherlockRequest('/entitlement', token), sherlockRequest('/requests', token)])
    if (generation.current !== epoch) return
    setAccess(eligibility); setRequests(history.requests)
    return token
  }

  async function open(id) {
    const epoch = generation.current
    setBusy(true); setError('')
    try {
      const token = await user.getIdToken()
      const result = await sherlockRequest(`/requests/${encodeURIComponent(id)}`, token)
      if (generation.current === epoch) setSelected(result)
    } catch (err) { if (generation.current === epoch) setError(err.message) }
    finally { if (generation.current === epoch) setBusy(false) }
  }

  async function submit(event) {
    event.preventDefault()
    const epoch = generation.current
    setBusy(true); setError('')
    const signature = JSON.stringify([question.trim(), scope.trim(), reportLength])
    if (submission.current?.signature !== signature) submission.current = { signature, key: crypto.randomUUID() }
    try {
      const token = await user.getIdToken()
      const result = await sherlockRequest('/requests', token, { method: 'POST', body: { question: question.trim(), scope: scope.trim(), reportLength, submissionKey: submission.current.key } })
      if (generation.current !== epoch) return
      setQuestion(''); setScope(''); setConsent(false); submission.current = null
      await refresh()
      if (generation.current !== epoch) return
      await open(result.id)
    } catch (err) { if (generation.current === epoch) setError(err.message) }
    finally { if (generation.current === epoch) setBusy(false) }
  }

  async function downloadPdf() {
    if (!selected?.report || downloading) return
    const epoch = generation.current
    setDownloading(true); setError('')
    try {
      const token = await user.getIdToken()
      const blob = await fetchSherlockPdf(selected.id, token)
      if (generation.current !== epoch) return
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url; link.download = 'weaware-sherlock-report.pdf'
      document.body.appendChild(link); link.click(); link.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (err) { if (generation.current === epoch) setError(err.message) }
    finally { if (generation.current === epoch) setDownloading(false) }
  }

  async function cancel(id) {
    const epoch = generation.current
    setBusy(true); setError('')
    try {
      const token = await user.getIdToken()
      await sherlockRequest(`/requests/${encodeURIComponent(id)}/cancel`, token, { method: 'POST' })
      await refresh()
      if (generation.current === epoch) setSelected(null)
    } catch (err) { if (generation.current === epoch) setError(err.message) }
    finally { if (generation.current === epoch) setBusy(false) }
  }

  return <div className="jeff-page">
    <header className="jeff-hero">
      <div className="jeff-eyebrow"><span className="jeff-dot" /> WeAware research desk · Private pilot</div>
      <div className="jeff-hero-row"><div><h1>Sherlock Mode<span>A question worth<br />looking into.</span></h1><p>Meet Journalist Jeff, your AI research assistant. Ask about an event, a claim, or a topic. Get a considered brief with the evidence open for inspection.</p></div><div className="jeff-emblem" aria-hidden="true"><Search strokeWidth={1} /><span>JJ / RESEARCH</span></div></div>
      <div className="jeff-principles"><span><BookOpen size={16} /> Sources you can inspect</span><span><ShieldCheck size={16} /> Checked before delivery</span><span><Clock3 size={16} /> Aiming for 24 hours</span></div>
    </header>
    {error && <div role="alert" className="jeff-alert">{error}</div>}
    {!ready || loading ? <p role="status" className="jeff-empty">Opening the research desk…</p> : !user ? <section className="jeff-panel jeff-empty"><h2>Your investigation starts here.</h2><p>Sign in with a verified email to check your pilot access. Reports stay private in your account.</p><button className="t-btn-primary jeff-button" onClick={requestSignIn}>Sign in to continue <ArrowUpRight size={16} /></button></section> : <>
      {!access?.eligible && <section className="jeff-panel jeff-empty"><h2>A small desk. A careful start.</h2><p>Sherlock Mode is available to invited testers. Ask the WeAware team for manual access using your signed-in account.</p></section>}
      {access?.eligible && <div className="jeff-desk-grid"><section className="jeff-panel">
        <div className="jeff-panel-heading"><h2>Give Jeff a lead</h2><span className="jeff-credit">{access.credits} {access.credits === 1 ? 'credit' : 'credits'} left</span></div>
        <p className="jeff-meta">One investigation uses one credit. Access ends {new Date(access.expiresAt).toLocaleDateString()}. Credits apply to this pilot period.</p>
        {!access.acceptingRequests && <p className="jeff-notice">The desk is paused while the pilot budget is checked. Existing reports remain available.</p>}
        {activeRequest && <p className="jeff-notice">One investigation at a time. Your current lead is {STATUS[activeRequest.status].toLowerCase()}.</p>}
        <form onSubmit={submit}>
          <label htmlFor="jeff-question">What would you like to understand?</label>
          <textarea id="jeff-question" required minLength={20} maxLength={1200} rows={4} value={question} onChange={event => setQuestion(event.target.value)} placeholder="What led to the recent event, which explanations are supported, and what is still disputed?" />
          <label htmlFor="jeff-scope">Set the boundaries <span className="jeff-meta">optional</span></label>
          <textarea id="jeff-scope" maxLength={600} rows={2} value={scope} onChange={event => setScope(event.target.value)} placeholder="Country, date range, or the particular angle you care about" />
          <label htmlFor="jeff-length">How much would you like to read?</label>
          <select id="jeff-length" value={reportLength} onChange={event => setReportLength(event.target.value)} aria-describedby="jeff-length-note">
            {Object.entries(LENGTHS).map(([value, length]) => <option key={value} value={value}>{length.label} · {length.words} words · {length.time}</option>)}
          </select>
          <p id="jeff-length-note" className="jeff-meta jeff-length-note">Choose the length of the analysis. Every approved report includes a readable PDF with linked sources. References are extra; research standards stay the same.</p>
          <label className="jeff-consent"><input type="checkbox" required checked={consent} onChange={event => setConsent(event.target.checked)} /><span>Use one credit for this private investigation. My question will be processed by WeAware’s research providers.</span></label>
          <button type="submit" className="t-btn-primary jeff-button" disabled={busy || !consent || !access.acceptingRequests || access.credits < 1 || Boolean(activeRequest)}>{busy ? 'Working…' : 'Send to Journalist Jeff'} <ArrowUpRight size={16} /></button>
        </form>
      </section><aside className="jeff-method"><p className="jeff-eyebrow">How Jeff works</p><h2>Follow the trail.<br />Question the story.</h2><ol><li><strong>Find the source.</strong> Search for primary material, independent reporting, and opposing evidence.</li><li><strong>Check the claims.</strong> Compare accounts and connect findings to passages in accessible sources.</li><li><strong>Show the workings.</strong> An editor reviews the brief before it appears here.</li></ol><p className="jeff-meta">In-depth means supported analysis, not a promise to find everything. Limited evidence or a failed investigation returns your credit. No billing or email in this pilot.</p></aside></div>}
      <section className="jeff-history" aria-labelledby="jeff-history-title"><div className="jeff-panel-heading"><h2 id="jeff-history-title">My investigations</h2><button disabled={busy} className="jeff-refresh" aria-label="Refresh investigations" onClick={async () => { setBusy(true); try { await refresh(); setError('') } catch (err) { setError(err.message) } finally { setBusy(false) } }}><RefreshCw size={16} /> Refresh</button></div>
        {!requests.length ? <p className="jeff-meta">Your research notebook is empty. Completed briefs will appear here.</p> : requests.map(item => <article className="jeff-history-item" key={item.id}><button disabled={busy} onClick={() => open(item.id)}><span className={`jeff-status jeff-status-${item.status}`}>{STATUS[item.status]}</span><h3>{item.question}</h3><span className="jeff-meta">{new Date(item.createdAt).toLocaleDateString()} · {LENGTHS[item.reportLength || 'standard'].label} {item.status === 'researching' ? `· ${STAGES[item.stage] || 'Research in progress'}` : ''}</span></button>{item.status === 'queued' && <button disabled={busy} className="jeff-cancel" onClick={() => cancel(item.id)}>Cancel & return credit</button>}</article>)}
      </section>
      {selected && <section className="jeff-selected" aria-live="polite"><div className="jeff-panel-heading"><p className="jeff-eyebrow">{STATUS[selected.status]}</p><button onClick={() => setSelected(null)} className="jeff-cancel">Close</button></div>{selected.report ? <ResearchReport investigation={selected} onDownload={downloadPdf} downloading={downloading} /> : <div className="jeff-panel"><h2>{selected.question}</h2><p>{selected.status === 'awaiting_review' ? 'Jeff’s draft is with the editor. It will appear here only after approval.' : ACTIVE.has(selected.status) ? `Jeff is working toward ${new Date(selected.dueAt).toLocaleString()}. This is an estimate; careful review may take longer.` : selected.status === 'cancelled' ? 'This investigation was cancelled and your credit returned.' : `${FAILURES[selected.errorCode] || 'This investigation could not be completed.'} Your credit has been returned.`}</p><p className="jeff-meta">Use Refresh, then open the investigation to see its latest status.</p></div>}</section>}
    </>}
    <footer className="jeff-footnote">Journalist Jeff is an AI assistant. Reports may contain errors. Follow the sources and use judgment for consequential decisions. Avoid sharing sensitive personal information. Raw research evidence has a 30-day retention policy; your private brief remains in your account.</footer>
  </div>
}
