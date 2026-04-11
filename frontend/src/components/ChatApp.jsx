import React, { useState, useEffect, useRef, useCallback } from 'react'
import { apiFetch, uploadFile, streamQuery, getAuth, clearAuth } from '../api.js'
import { getStore, setStore, saveSession, deleteSessionFromStore, newLocalId, relativeTime } from '../store.js'
import Message, { ThinkingMessage, StreamingMessage } from './Message.jsx'

const EXAMPLE_QUERIES = [
  'Summarise this document',
  'What are the key findings?',
  'Show data as a table',
  'List the main topics covered',
]

/* ── Initial blank session ── */
function blankSession() {
  return {
    id: newLocalId(),
    title: 'New Chat',
    sessionId: null,
    documentIds: [],
    docStatuses: {},
    messages: [],
  }
}

export default function ChatApp({ onLogout, showToast }) {
  const auth = getAuth()

  const [session, setSession] = useState(() => {
    const s = getStore()
    if (s.currentId && s.sessions[s.currentId]) {
      const saved = s.sessions[s.currentId]
      return {
        id: saved.id,
        title: saved.title,
        sessionId: saved.sessionId,
        documentIds: saved.documentIds || [],
        docStatuses: saved.docStatuses || {},
        messages: saved.messages || [],
      }
    }
    return blankSession()
  })

  // streaming state
  const [isLoading, setIsLoading] = useState(false)
  const [streamingTokens, setStreamingTokens] = useState('')
  const [streamingCitations, setStreamingCitations] = useState([])
  const [streamingConfidence, setStreamingConfidence] = useState(null)
  const [isStreaming, setIsStreaming] = useState(false)

  // input
  const [inputValue, setInputValue] = useState('')
  const textareaRef = useRef(null)
  const messagesEndRef = useRef(null)
  const fileInputRef = useRef(null)
  const uploadZoneRef = useRef(null)

  // history sidebar re-render trigger
  const [historyVersion, setHistoryVersion] = useState(0)

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  // On mount: verify backend session, refresh docs, restore history
  useEffect(() => {
    async function init() {
      const s = getStore()
      if (s.currentId && s.sessions[s.currentId]) {
        const saved = s.sessions[s.currentId]
        await loadSession(saved.id, false)
      } else {
        // Still refresh doc statuses for sidebar
        await refreshDocStatuses()
      }
      setHistoryVersion(v => v + 1)
    }
    init()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Persist session whenever it changes
  useEffect(() => {
    if (session.id) {
      saveSession(session)
      setHistoryVersion(v => v + 1)
    }
  }, [session])

  useEffect(() => { scrollToBottom() }, [session.messages, isStreaming, scrollToBottom])

  /* ── Doc library refresh ── */
  async function refreshDocStatuses() {
    try {
      const data = await apiFetch('/api/v1/documents')
      const docs = data.documents || []
      const docStatuses = {}
      const documentIds = []
      for (const doc of docs) {
        documentIds.push(doc.document_id)
        docStatuses[doc.document_id] = {
          name: doc.filename,
          status: doc.status,
          chunks: doc.total_chunks,
          pages: doc.page_count,
        }
      }
      setSession(prev => ({ ...prev, docStatuses, documentIds }))
      return { docStatuses, documentIds }
    } catch {
      return null
    }
  }

  /* ── Auto-renew expired session ── */
  async function autoRenewSession(currentDocStatuses) {
    try {
      const statuses = currentDocStatuses || session.docStatuses
      const hasReady = Object.values(statuses).some(d => d.status === 'ready')
      if (!hasReady) return false
      const sess = await apiFetch('/api/v1/sessions', 'POST', {})
      setSession(prev => ({
        ...prev,
        sessionId: sess.session_id,
        documentIds: sess.document_ids,
      }))
      if (sess.document_ids.length > 0) {
        showToast('Session renewed — your documents are still available.', 'success')
        return true
      }
      return false
    } catch {
      return false
    }
  }

  /* ── Load a session from localStorage ── */
  async function loadSession(localId, saveFirst = true) {
    if (saveFirst && session.id && session.sessionId) {
      saveSession(session)
    }
    const s = getStore()
    const saved = s.sessions[localId]
    if (!saved) return

    // Verify backend session alive
    let backendAlive = false
    if (saved.sessionId) {
      try {
        await apiFetch(`/api/v1/sessions/${saved.sessionId}`)
        backendAlive = true
      } catch { backendAlive = false }
    }

    const newSess = {
      id: saved.id,
      title: saved.title,
      sessionId: backendAlive ? saved.sessionId : null,
      documentIds: backendAlive ? (saved.documentIds || []) : [],
      docStatuses: saved.docStatuses || {},
      messages: saved.messages || [],
    }
    setSession(newSess)

    if (!backendAlive) {
      // Try auto-renew
      await autoRenewSession(newSess.docStatuses)
    }
    setHistoryVersion(v => v + 1)
  }

  /* ── New Chat ── */
  function newChat() {
    if (session.id && session.sessionId) saveSession(session)
    const fresh = blankSession()
    const s = getStore()
    s.currentId = fresh.id
    setStore(s)
    setSession(fresh)
    setHistoryVersion(v => v + 1)
  }

  /* ── Delete session ── */
  function deleteSession(e, localId) {
    e.stopPropagation()
    deleteSessionFromStore(localId)
    if (session.id === localId) newChat()
    else setHistoryVersion(v => v + 1)
  }

  /* ── Upload ── */
  async function handleUpload(file) {
    if (!file || file.type !== 'application/pdf') {
      showToast('Please upload a PDF file.', 'error')
      return
    }

    // Ensure we have a backend session
    let sid = session.sessionId
    if (!sid) {
      try {
        const sess = await apiFetch('/api/v1/sessions', 'POST', {})
        sid = sess.session_id
        setSession(prev => ({ ...prev, sessionId: sid }))
      } catch (err) {
        if (err.sessionExpired) { onLogout(); return }
        showToast('Could not create session: ' + err.message, 'error')
        return
      }
    }

    try {
      const data = await uploadFile(file, sid)
      const docId = data.document_id

      setSession(prev => ({
        ...prev,
        documentIds: [...new Set([...prev.documentIds, docId])],
        docStatuses: {
          ...prev.docStatuses,
          [docId]: { name: file.name, status: 'processing' },
        },
        // Set title from first doc if still default
        title: prev.title === 'New Chat' ? file.name.replace(/\.pdf$/i, '') : prev.title,
      }))
      showToast('Uploaded — processing…')

      await pollDocument(docId, file.name)
    } catch (err) {
      if (err.sessionExpired) { onLogout(); return }
      showToast(err.message, 'error')
    }
  }

  async function pollDocument(docId, fileName) {
    for (let i = 0; i < 40; i++) {
      await sleep(3000)
      try {
        const doc = await apiFetch(`/api/v1/documents/${docId}`)
        setSession(prev => ({
          ...prev,
          docStatuses: {
            ...prev.docStatuses,
            [docId]: {
              name: prev.docStatuses[docId]?.name || fileName || docId,
              status: doc.status,
              chunks: doc.total_chunks,
              pages: doc.page_count,
            },
          },
        }))
        if (doc.status === 'ready') {
          showToast(`Ready — ${doc.total_chunks} chunk(s) indexed.`, 'success')
          return
        }
        if (doc.status === 'error') {
          showToast('Processing failed. Try another file.', 'error')
          return
        }
      } catch {}
    }
    showToast('Processing is taking long. Check server logs.', 'error')
  }

  /* ── Send message ── */
  async function sendMessage() {
    const text = inputValue.trim()
    if (!text || isLoading) return
    if (!session.sessionId || session.documentIds.length === 0) {
      showToast('Upload a document first.', 'error')
      return
    }

    const newMessages = [...session.messages, { role: 'user', text }]
    setSession(prev => ({ ...prev, messages: newMessages }))
    setInputValue('')
    resetTextarea()
    setIsLoading(true)
    setIsStreaming(true)
    setStreamingTokens('')
    setStreamingCitations([])
    setStreamingConfidence(null)

    try {
      const { fullText, citations, confidence } = await streamQuery(
        { question: text, sessionId: session.sessionId, documentIds: session.documentIds },
        {
          onToken: delta => setStreamingTokens(prev => prev + delta),
          onCitation: c => setStreamingCitations(c),
          onDone: c => setStreamingConfidence(c),
          onError: msg => { throw new Error(msg) },
        }
      )
      setIsStreaming(false)
      setSession(prev => ({
        ...prev,
        messages: [
          ...prev.messages,
          { role: 'assistant', text: fullText, citations, confidence },
        ],
      }))
    } catch (err) {
      setIsStreaming(false)
      if (err.sessionExpired) { onLogout(); return }
      setSession(prev => ({
        ...prev,
        messages: [
          ...prev.messages,
          { role: 'assistant', text: `Error: ${err.message}`, citations: [], confidence: null },
        ],
      }))
    } finally {
      setIsLoading(false)
    }
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
  }

  function resetTextarea() {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  function handleInputChange(e) {
    setInputValue(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  }

  function useExample(text) {
    if (session.documentIds.length === 0) { showToast('Upload a PDF first.', 'error'); return }
    setInputValue(text)
    textareaRef.current?.focus()
  }

  /* ── Drag/drop ── */
  function handleDragOver(e) { e.preventDefault(); uploadZoneRef.current?.classList.add('drag-over') }
  function handleDragLeave() { uploadZoneRef.current?.classList.remove('drag-over') }
  function handleDrop(e) {
    e.preventDefault()
    uploadZoneRef.current?.classList.remove('drag-over')
    const file = e.dataTransfer.files[0]
    if (file && file.type === 'application/pdf') handleUpload(file)
    else showToast('Please drop a PDF file.', 'error')
  }

  /* ── Logout ── */
  async function handleLogout() {
    try { await apiFetch('/api/v1/auth/logout', 'POST').catch(() => {}) } catch {}
    onLogout()
  }

  /* ── Derived ── */
  const hasReady = Object.values(session.docStatuses).some(d => d.status === 'ready')
  const chatEnabled = hasReady && !!session.sessionId
  const userInitial = (auth?.name || auth?.email || 'U').charAt(0).toUpperCase()
  const userDisplay = auth?.name || auth?.email || ''

  /* ── Chat history list ── */
  const allSessions = Object.values(getStore().sessions).sort(
    (a, b) => new Date(b.lastActiveAt) - new Date(a.lastActiveAt)
  )

  return (
    <div className="app">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="sidebar-top">
          <div className="logo">
            <div className="logo-mark-sm">D</div>
            <span className="logo-text">DocMind</span>
          </div>
          <button className="btn-new-chat" onClick={newChat} title="New Chat">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            New Chat
          </button>
        </div>

        {/* Recent chats */}
        <div className="sidebar-section">
          <div className="sidebar-section-label">Recent Chats</div>
          <div className="chat-history-list">
            {allSessions.length === 0 ? (
              <div className="no-history">No chats yet</div>
            ) : allSessions.map(sess => {
              const isActive = sess.id === session.id
              const preview = sess.messages.find(m => m.role === 'user')?.text?.slice(0, 45) || 'No messages yet'
              return (
                <div
                  key={sess.id}
                  className={`chat-history-item${isActive ? ' active' : ''}`}
                  onClick={() => loadSession(sess.id)}
                >
                  <div className="chi-icon">💬</div>
                  <div className="chi-body">
                    <div className="chi-title">{sess.title}</div>
                    <div className="chi-preview">{preview}</div>
                    <div className="chi-time">{relativeTime(sess.lastActiveAt)}</div>
                  </div>
                  <button
                    className="chi-delete"
                    title="Delete"
                    onClick={e => deleteSession(e, sess.id)}
                  >✕</button>
                </div>
              )
            })}
          </div>
        </div>

        <div className="sidebar-divider"></div>

        {/* Upload */}
        <div className="sidebar-section">
          <div className="sidebar-section-label">Upload Document</div>
          <div
            ref={uploadZoneRef}
            className="upload-zone"
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={e => { if (e.target === e.currentTarget || e.target.closest('.upload-zone') === e.currentTarget) fileInputRef.current?.click() }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              style={{ display: 'none' }}
              onChange={e => {
                const file = e.target.files[0]
                if (file) handleUpload(file)
                e.target.value = ''
              }}
            />
            <div className="upload-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="12" y1="18" x2="12" y2="12"/>
                <line x1="9" y1="15" x2="15" y2="15"/>
              </svg>
            </div>
            <p className="upload-label">Drop PDF here or</p>
            <button className="btn-browse" onClick={() => fileInputRef.current?.click()} type="button">
              Browse file
            </button>
          </div>

          {/* Doc list */}
          <div className="doc-list">
            {Object.entries(session.docStatuses).map(([id, info]) => (
              <div className="doc-card" key={id}>
                <div className="doc-card-icon">📄</div>
                <div className="doc-card-info">
                  <div className="doc-card-name" title={info.name}>{info.name}</div>
                  <div className="doc-card-meta">{info.pages ? `${info.pages} page(s)` : ''}</div>
                  {info.status === 'processing' && (
                    <span className="doc-status-badge processing">
                      <span className="spinner"></span> Processing
                    </span>
                  )}
                  {info.status === 'ready' && (
                    <span className="doc-status-badge ready">
                      ✓ Ready · {info.chunks || '?'} chunks
                    </span>
                  )}
                  {info.status === 'error' && (
                    <span className="doc-status-badge error">✗ Error</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="sidebar-footer">
          <div className="footer-user-info">
            <div className="footer-avatar">{userInitial}</div>
            <div className="footer-user-text">
              <span className="footer-user-email">{userDisplay}</span>
            </div>
          </div>
          <button className="btn-signout" onClick={handleLogout} title="Sign out">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
              <polyline points="16 17 21 12 16 7"/>
              <line x1="21" y1="12" x2="9" y2="12"/>
            </svg>
          </button>
        </div>
      </aside>

      {/* ── Chat main ── */}
      <main className="chat-main">
        <div className="chat-messages">
          {/* Welcome screen */}
          {session.messages.length === 0 && !isStreaming && (
            <div className="welcome" id="welcomeScreen">
              <div className="welcome-graphic">
                <div className="welcome-icon-ring">
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                    <line x1="16" y1="13" x2="8" y2="13"/>
                    <line x1="16" y1="17" x2="8" y2="17"/>
                    <polyline points="10 9 9 9 8 9"/>
                  </svg>
                </div>
              </div>
              <h2 className="welcome-title">Ask anything about your PDF</h2>
              <p className="welcome-sub">Upload a document in the sidebar, then ask away.</p>
              <div className="example-queries">
                {EXAMPLE_QUERIES.map(q => (
                  <button key={q} className="example-chip" onClick={() => useExample(q)} type="button">
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Messages */}
          {session.messages.map((msg, i) => (
            <Message
              key={i}
              role={msg.role}
              text={msg.text}
              citations={msg.citations}
              confidence={msg.confidence}
            />
          ))}

          {/* Streaming / thinking */}
          {isLoading && !isStreaming && <ThinkingMessage />}
          {isStreaming && streamingTokens === '' && <ThinkingMessage />}
          {isStreaming && streamingTokens !== '' && (
            <StreamingMessage
              tokens={streamingTokens}
              citations={streamingCitations}
              confidence={streamingConfidence}
            />
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input bar */}
        <div className="input-area">
          <div className="input-bar">
            <textarea
              ref={textareaRef}
              className="message-textarea"
              placeholder={chatEnabled ? 'Ask a question about your document…' : 'Upload a PDF to start chatting…'}
              rows={1}
              disabled={isLoading || !chatEnabled}
              value={inputValue}
              onChange={handleInputChange}
              onKeyDown={handleKey}
            />
            <button
              id="sendBtn"
              className="send-btn"
              onClick={sendMessage}
              disabled={isLoading || !chatEnabled || !inputValue.trim()}
              title="Send (Enter)"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
              </svg>
            </button>
          </div>
          <p className="input-hint">Responses are grounded in your uploaded document.</p>
        </div>
      </main>
    </div>
  )
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)) }
