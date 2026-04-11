import React, { useState, useEffect, useRef } from 'react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.use({ gfm: true, breaks: true })

function renderMarkdown(text) {
  return DOMPurify.sanitize(marked.parse(text || ''))
}

/* ── Citations ── */
function Citations({ citations }) {
  if (!citations || citations.length === 0) return null
  return (
    <div className="citations-block">
      <div className="citations-label">{citations.length} Source{citations.length > 1 ? 's' : ''}</div>
      <div className="citations-chips">
        {citations.map((c, i) => {
          const pages = (c.page_numbers || []).join(', ')
          return (
            <div className="citation-chip" key={i} title={c.excerpt || ''}>
              <span className="citation-chip-doc">[{i + 1}]</span>
              {c.document_name}{pages ? ` · p. ${pages}` : ''}
            </div>
          )
        })}
      </div>
    </div>
  )
}

/* ── Confidence badge ── */
function ConfidenceBadge({ score }) {
  if (score === null || score === undefined) return null
  const pct = Math.round(score * 100)
  const color = score >= 0.65 ? 'var(--accent)' : score >= 0.4 ? 'var(--warning)' : 'var(--danger)'
  return (
    <div style={{ fontSize: '11px', color: 'var(--text-faint)', marginTop: '10px', paddingLeft: '38px' }}>
      <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: color, marginRight: 5, verticalAlign: 'middle' }} />
      Confidence {pct}%
    </div>
  )
}

/* ── Thinking dots ── */
export function ThinkingMessage() {
  return (
    <div className="message-row assistant">
      <div className="message-header">
        <div className="msg-avatar ai-av">D</div>
      </div>
      <div className="message-bubble">
        <div className="thinking-dots">
          <span /><span /><span />
        </div>
      </div>
    </div>
  )
}

/* ── Streaming message ── */
export function StreamingMessage({ tokens, citations, confidence }) {
  const contentRef = useRef(null)

  useEffect(() => {
    if (contentRef.current) {
      contentRef.current.textContent = tokens
    }
  }, [tokens])

  return (
    <div className="message-row assistant">
      <div className="message-header">
        <div className="msg-avatar ai-av">D</div>
        <span className="msg-role">DocMind</span>
      </div>
      <div className="message-bubble">
        <div className="md-body" ref={contentRef} />
        <span className="stream-cursor" />
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
      <div className="message-row user">
        <div className="message-header" style={{ justifyContent: 'flex-end' }}>
          <span className="msg-role">You</span>
          <div className="msg-avatar user-av">U</div>
        </div>
        <div className="message-bubble">
          {text}
        </div>
      </div>
    )
  }

  const isError = text && text.startsWith('Error:')
  return (
    <div className="message-row assistant">
      <div className="message-header">
        <div className="msg-avatar ai-av">D</div>
        <span className="msg-role">DocMind</span>
      </div>
      <div className="message-bubble">
        {isError ? (
          <div className="message-error">{text}</div>
        ) : (
          <div
            className="md-body"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(text) }}
          />
        )}
        <Citations citations={citations} />
        <ConfidenceBadge score={confidence} />
      </div>
    </div>
  )
}
