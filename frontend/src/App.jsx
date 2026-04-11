import React, { useState, useEffect, useCallback } from 'react'
import AuthPage from './components/AuthPage.jsx'
import ChatApp from './components/ChatApp.jsx'
import { getAuth, setAuth, clearAuth } from './api.js'

export default function App() {
  const [authed, setAuthed] = useState(false)
  const [toastMsg, setToastMsg] = useState('')
  const [toastType, setToastType] = useState('')
  const [toastVisible, setToastVisible] = useState(false)
  const [resetToken, setResetToken] = useState(null)
  const [authTab, setAuthTab] = useState('login')

  let _toastTimer = null

  const showToast = useCallback((msg, type = '') => {
    setToastMsg(msg)
    setToastType(type)
    setToastVisible(true)
    clearTimeout(_toastTimer)
    _toastTimer = setTimeout(() => setToastVisible(false), 3000)
  }, [])

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search)
    const oauthToken = urlParams.get('access_token')
    const authError = urlParams.get('auth_error')

    if (window.location.pathname === '/reset-password') {
      const tok = urlParams.get('token')
      history.replaceState({}, '', '/')
      if (tok) {
        setResetToken(tok)
      } else {
        showToast('Invalid reset link. Please request a new one.', 'error')
      }
    } else if (oauthToken) {
      setAuth({
        token: oauthToken,
        user_id: urlParams.get('user_id') || '',
        email: urlParams.get('email') || '',
        name: urlParams.get('name') || '',
      })
      history.replaceState({}, '', window.location.pathname)
      setAuthed(true)
    } else if (authError) {
      showToast('Google sign-in failed. Please try again.', 'error')
      history.replaceState({}, '', window.location.pathname)
    }

    // Check stored auth
    const auth = getAuth()
    if (auth?.token) {
      setAuthed(true)
    }
  }, [])

  function handleLogin() {
    setResetToken(null)
    setAuthed(true)
  }

  function handleLogout() {
    clearAuth()
    setAuthed(false)
    setAuthTab('login')
  }

  return (
    <>
      {authed ? (
        <ChatApp onLogout={handleLogout} showToast={showToast} />
      ) : (
        <AuthPage
          onLogin={handleLogin}
          showToast={showToast}
          initialTab={authTab}
          resetToken={resetToken}
        />
      )}

      {/* Toast */}
      <div
        className={`toast${toastVisible ? ' show' : ''}${toastType ? ' ' + toastType : ''}`}
        role="status"
        aria-live="polite"
      >
        {toastMsg}
      </div>
    </>
  )
}
