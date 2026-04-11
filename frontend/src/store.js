const STORE_KEY = 'rag_store'

export function getStore() {
  try { return JSON.parse(localStorage.getItem(STORE_KEY)) || { currentId: null, sessions: {} } }
  catch { return { currentId: null, sessions: {} } }
}

export function setStore(s) {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(s)) } catch {}
}

export function newLocalId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2)
}

export function saveSession(state) {
  if (!state.id) return
  const s = getStore()
  s.sessions[state.id] = {
    id:          state.id,
    title:       state.title,
    sessionId:   state.sessionId,
    documentIds: state.documentIds,
    docStatuses: state.docStatuses,
    messages:    state.messages,
    lastActiveAt: new Date().toISOString(),
  }
  s.currentId = state.id
  setStore(s)
}

export function deleteSessionFromStore(localId) {
  const s = getStore()
  delete s.sessions[localId]
  if (s.currentId === localId) s.currentId = null
  setStore(s)
  return s
}

export function relativeTime(iso) {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}
