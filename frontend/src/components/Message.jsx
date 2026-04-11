import React, { useState, useEffect, useRef } from 'react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.use({ gfm: true, breaks: true })

function renderMarkdown(text) {
  return DOMPurify.sanitize(marked.parse(text || ''))
}

/* ── Citations collapsible ── */
function Citations({ citations }) {
  const [open, setOpen] = useState(false)
  if (!citations || citations.length === 0) return null
  return (
    <div className="citations">
      <button className="citations-toggle" onClick={() => setOpen(o => !o)}>
        <span>📎</span> {citations.length} Source{citations.length > 1 ? 's' : ''} {open ? '▲' : ''}
      </button>
      {open && (
        <div className="citations-list">
          {citations.map((c, i) => {
            const pages = (c.page_numbers || []).join(', ')
            return (
              <div className="citation-item" key={i}>
                <div className="citation-source">
                  Source {i + 1} — {c.document_name}{pages ? `, p. ${pages}` : ''}
                </div>
                <div className="citation-excerpt">"{(c.excerpt || '').trim()}"</div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

/* ── Confidence badge ── */
function ConfidenceBadge({ score }) {
  if (score === null || score === undefined) return null
  const pct = Math.round(score * 100)
  const cls = score >= 0.65 ? 'conf-high' : score >= 0.4 ? 'conf-medium' : 'conf-low'
  const label = score >= 0.65 ? 'High' : score >= 0.4 ? 'Medium' : 'Low'
  return (
    <div className="confidence-badge">
      <span className={`conf-dot ${cls}`}></span> Confidence: {label} ({pct}%)
    </div>
  )
}

/* ── Thinking dots ── */
export function ThinkingMessage() {
  return (
    <div className="msg-row assistant">
      <div className="msg-avatar">D</div>
      <div className="msg-bubble">
        <div className="thinking-dots">
          <span></span><span></span><span></span>
        </div>
      </div>
    </div>
  )
}

/* ── Streaming message — receives tokens in real time ── */
export function StreamingMessage({ tokens, citations, confidence }) {
  const contentRef = useRef(null)
  const rawRef = useRef('')

  useEffect(() => {
    rawRef.current = tokens
    if (contentRef.current) {
      // During streaming show raw text with cursor; after streaming render markdown
      contentRef.current.textContent = tokens
    }
  }, [tokens])

  return (
    <div className="msg-row assistant">
      <div className="msg-avatar">D</div>
      <div className="msg-bubble">
        <div
          className="msg-content typing-cursor"
          ref={contentRef}
        />
        {citations && citations.length > 0 && <Citations citations={citations} />}
        {confidence !== null && confidence !== undefined && <ConfidenceBadge score={confidence} />}
      </div>
    </div>
  )
}

/* ── Completed message ── */
export default function Message({ role, text, citations, confidence }) {
  if (role === 'user') {
    return (
      <div className="msg-row user">
        <div className="msg-avatar">U</div>
        <div className="msg-bubble">
          <div className="msg-content">{text}</div>
        </div>
      </div>
    )
  }

  const isError = text && text.startsWith('Error:')
  return (
    <div className="msg-row assistant">
      <div className="msg-avatar">D</div>
      <div className="msg-bubble">
        {isError ? (
          <div className="msg-content msg-error">{text}</div>
        ) : (
          <div
            className="msg-content markdown-body"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(text) }}
          />
        )}
        <Citations citations={citations} />
        <ConfidenceBadge score={confidence} />
      </div>
    </div>
  )
}
