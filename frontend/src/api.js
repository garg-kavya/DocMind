const AUTH_KEY = 'rag_auth'

export function getAuth() {
  try { return JSON.parse(localStorage.getItem(AUTH_KEY)) || null } catch { return null }
}
export function setAuth(a) { localStorage.setItem(AUTH_KEY, JSON.stringify(a)) }
export function clearAuth() { localStorage.removeItem(AUTH_KEY) }

/**
 * Central fetch helper. Throws on non-2xx.
 * Throws a special { sessionExpired: true } error on 401.
 */
export async function apiFetch(path, method = 'GET', body = undefined) {
  const auth = getAuth()
  const headers = { 'Content-Type': 'application/json' }
  if (auth?.token) headers['Authorization'] = `Bearer ${auth.token}`
  const opts = { method, headers }
  if (body !== undefined) opts.body = JSON.stringify(body)
  const resp = await fetch(path, opts)
  if (resp.status === 401) {
    const err = new Error('session-expired')
    err.sessionExpired = true
    throw err
  }
  if (!resp.ok) {
    const e = await resp.json().catch(() => ({}))
    throw new Error(e?.detail || e?.error?.message || `Request failed (${resp.status})`)
  }
  return resp.json()
}

/**
 * Upload file via multipart form. Returns parsed JSON.
 * Throws { sessionExpired } on 401.
 */
export async function uploadFile(file, sessionId) {
  const auth = getAuth()
  const headers = {}
  if (auth?.token) headers['Authorization'] = `Bearer ${auth.token}`
  const form = new FormData()
  form.append('file', file)
  form.append('session_id', sessionId)
  const resp = await fetch('/api/v1/documents/upload', { method: 'POST', headers, body: form })
  if (resp.status === 401) {
    const err = new Error('session-expired')
    err.sessionExpired = true
    throw err
  }
  if (!resp.ok) {
    const e = await resp.json().catch(() => ({}))
    throw new Error(e?.error?.message || `Upload failed (${resp.status})`)
  }
  return resp.json()
}

/**
 * Opens an SSE stream to /api/v1/query/stream.
 * Calls callbacks: onToken(delta), onCitation(citations[]), onDone(confidence), onError(msg).
 * Returns { fullText, citations, confidence }.
 */
export async function streamQuery({ question, sessionId, documentIds }, callbacks) {
  const { onToken, onCitation, onDone, onError } = callbacks
  const auth = getAuth()
  const headers = { 'Content-Type': 'application/json' }
  if (auth?.token) headers['Authorization'] = `Bearer ${auth.token}`

  const resp = await fetch('/api/v1/query/stream', {
    method: 'POST',
    headers,
    body: JSON.stringify({ question, session_id: sessionId, document_ids: documentIds }),
  })

  if (resp.status === 401) {
    const err = new Error('session-expired')
    err.sessionExpired = true
    throw err
  }
  if (!resp.ok) {
    const e = await resp.json().catch(() => ({}))
    throw new Error(e?.detail || e?.error?.message || `Server error (${resp.status})`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let fullText = ''
  let citations = []
  let confidence = null
  let eventName = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split(/\n\n/)
    buffer = parts.pop()

    for (const part of parts) {
      for (const line of part.split('\n')) {
        if (line.startsWith('event: ')) {
          eventName = line.slice(7).trim()
        } else if (line.startsWith('data: ')) {
          const raw = line.slice(6).trim()
          if (!raw) continue
          let data
          try { data = JSON.parse(raw) } catch { continue }

          if (eventName === 'token') {
            const delta = data.text || ''
            if (!delta) continue
            fullText += delta
            onToken(delta)
          } else if (eventName === 'citation') {
            citations = data.citations || []
            onCitation(citations)
          } else if (eventName === 'done') {
            confidence = data.confidence ?? null
            onDone(confidence)
          } else if (eventName === 'error') {
            onError(data.message || 'Stream error')
            return { fullText, citations, confidence }
          }
        }
      }
    }
  }

  return { fullText: fullText || '(No response)', citations, confidence }
}
