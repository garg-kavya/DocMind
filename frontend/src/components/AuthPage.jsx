import React, { useState, useEffect, useRef } from 'react'
import { apiFetch, setAuth } from '../api.js'

const GoogleIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
  </svg>
)

/* ── Forgot Password Modal ── */
function ForgotPasswordModal({ onClose, showToast }) {
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => {
    setTimeout(() => inputRef.current?.focus(), 50)
  }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    setError(''); setSuccess('')
    setLoading(true)
    try {
      await apiFetch('/api/v1/auth/forgot-password', 'POST', { email })
      setSuccess('If that email is registered, a reset link has been sent.')
    } catch (err) {
      if (err.message.includes('not configured')) {
        setError('Email service is not configured on this server.')
      } else {
        setError(err.message)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="modal-card" role="dialog" aria-modal="true" aria-labelledby="forgotTitle">
        <div className="modal-header">
          <h3 className="modal-title" id="forgotTitle">Reset password</h3>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <p className="modal-desc">We'll send a password reset link to your email.</p>
        <form onSubmit={handleSubmit} noValidate>
          <div className="form-group">
            <label className="form-label" htmlFor="forgotEmail">Email address</label>
            <input
              ref={inputRef}
              className="form-input"
              type="email"
              id="forgotEmail"
              placeholder="you@example.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
            />
          </div>
          {error && <div className="auth-error">{error}</div>}
          {success && <div className="auth-success">{success}</div>}
          <button className="btn-primary" type="submit" disabled={loading}>
            {loading ? 'Sending…' : success ? 'Sent' : 'Send Reset Link'}
          </button>
        </form>
      </div>
    </div>
  )
}

/* ── Reset Password Modal ── */
function ResetPasswordModal({ token, onSuccess, showToast }) {
  const [pw, setPw] = useState('')
  const [pwConf, setPwConf] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => {
    setTimeout(() => inputRef.current?.focus(), 50)
  }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    setError(''); setSuccess('')
    if (pw !== pwConf) { setError('Passwords do not match.'); return }
    if (pw.length < 8) { setError('Password must be at least 8 characters.'); return }
    setLoading(true)
    try {
      const data = await apiFetch('/api/v1/auth/reset-password', 'POST', { token, new_password: pw })
      setAuth({ token: data.access_token, user_id: data.user_id, email: data.email, name: data.name || '' })
      setSuccess('Password updated! Signing you in…')
      setTimeout(() => onSuccess(), 1500)
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="modal-card" role="dialog" aria-modal="true" aria-labelledby="resetTitle">
        <div className="modal-header">
          <h3 className="modal-title" id="resetTitle">Set new password</h3>
        </div>
        <p className="modal-desc">Enter and confirm your new password below.</p>
        <form onSubmit={handleSubmit} noValidate>
          <div className="form-group">
            <label className="form-label" htmlFor="resetPassword">
              New password <span className="form-hint">min 8 characters</span>
            </label>
            <input
              ref={inputRef}
              className="form-input"
              type="password"
              id="resetPassword"
              placeholder="••••••••"
              value={pw}
              onChange={e => setPw(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="resetPasswordConfirm">Confirm password</label>
            <input
              className="form-input"
              type="password"
              id="resetPasswordConfirm"
              placeholder="••••••••"
              value={pwConf}
              onChange={e => setPwConf(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
            />
          </div>
          {error && <div className="auth-error">{error}</div>}
          {success && <div className="auth-success">{success}</div>}
          <button className="btn-primary" type="submit" disabled={loading}>
            {loading ? 'Saving…' : 'Set New Password'}
          </button>
        </form>
      </div>
    </div>
  )
}

/* ── Main AuthPage ── */
export default function AuthPage({ onLogin, showToast, initialTab = 'login', resetToken = null }) {
  const [tab, setTab] = useState(initialTab)
  const [googleHidden, setGoogleHidden] = useState(false)
  const [showForgot, setShowForgot] = useState(false)
  const [showReset, setShowReset] = useState(!!resetToken)
  const [resetTok, setResetTok] = useState(resetToken || '')

  // Login form state
  const [loginEmail, setLoginEmail] = useState('')
  const [loginPw, setLoginPw] = useState('')
  const [loginError, setLoginError] = useState('')
  const [loginLoading, setLoginLoading] = useState(false)

  // Register form state
  const [regEmail, setRegEmail] = useState('')
  const [regPw, setRegPw] = useState('')
  const [regError, setRegError] = useState('')
  const [regLoading, setRegLoading] = useState(false)

  useEffect(() => {
    // Check if Google OAuth is configured
    fetch('/api/v1/auth/google', { redirect: 'manual' })
      .then(r => { if (r.status === 501) setGoogleHidden(true) })
      .catch(() => {})
  }, [])

  function switchTab(t) {
    setTab(t)
    setLoginError('')
    setRegError('')
  }

  async function handleGoogleLogin() {
    try {
      const resp = await fetch('/api/v1/auth/google', { redirect: 'manual' })
      if (resp.type === 'opaqueredirect' || resp.status === 0) {
        window.location.href = '/api/v1/auth/google'
      } else if (resp.status === 501) {
        showToast('Google sign-in is not configured on this server.', 'error')
      } else {
        window.location.href = '/api/v1/auth/google'
      }
    } catch {
      window.location.href = '/api/v1/auth/google'
    }
  }

  async function handleLogin(e) {
    e.preventDefault()
    setLoginError('')
    setLoginLoading(true)
    try {
      const data = await apiFetch('/api/v1/auth/login', 'POST', { email: loginEmail, password: loginPw })
      setAuth({ token: data.access_token, user_id: data.user_id, email: data.email, name: data.name || '' })
      onLogin()
    } catch (err) {
      setLoginError(err.message)
    } finally {
      setLoginLoading(false)
    }
  }

  async function handleRegister(e) {
    e.preventDefault()
    setRegError('')
    setRegLoading(true)
    try {
      const data = await apiFetch('/api/v1/auth/register', 'POST', { email: regEmail, password: regPw })
      setAuth({ token: data.access_token, user_id: data.user_id, email: data.email, name: data.name || '' })
      onLogin()
    } catch (err) {
      setRegError(err.message)
    } finally {
      setRegLoading(false)
    }
  }

  return (
    <div className="auth-overlay">
      <div className="auth-bg-shapes" aria-hidden="true">
        <div className="shape shape-1"></div>
        <div className="shape shape-2"></div>
        <div className="shape shape-3"></div>
      </div>

      <div className="auth-card">
        <div className="auth-header">
          <div className="auth-logo">
            <div className="logo-mark">D</div>
            <span className="logo-wordmark">DocMind</span>
          </div>
          <p className="auth-tagline">AI-powered document intelligence</p>
        </div>

        <div className="auth-tabs" role="tablist">
          <button
            className={`auth-tab${tab === 'login' ? ' active' : ''}`}
            role="tab"
            onClick={() => switchTab('login')}
          >Sign In</button>
          <button
            className={`auth-tab${tab === 'register' ? ' active' : ''}`}
            role="tab"
            onClick={() => switchTab('register')}
          >Create Account</button>
        </div>

        {/* Login Panel */}
        <div className={`auth-panel${tab !== 'login' ? ' hidden' : ''}`}>
          {!googleHidden && (
            <>
              <button className="btn-google" onClick={handleGoogleLogin} type="button">
                <GoogleIcon /> Continue with Google
              </button>
              <div className="auth-divider"><span>or continue with email</span></div>
            </>
          )}
          <form onSubmit={handleLogin} noValidate>
            <div className="form-group">
              <label className="form-label" htmlFor="loginEmail">Email</label>
              <input
                className="form-input"
                type="email"
                id="loginEmail"
                placeholder="you@example.com"
                value={loginEmail}
                onChange={e => setLoginEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>
            <div className="form-group">
              <div className="form-label-row">
                <label className="form-label" htmlFor="loginPassword">Password</label>
                <a className="forgot-link" href="#" onClick={e => { e.preventDefault(); setShowForgot(true) }}>
                  Forgot password?
                </a>
              </div>
              <input
                className="form-input"
                type="password"
                id="loginPassword"
                placeholder="••••••••"
                value={loginPw}
                onChange={e => setLoginPw(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>
            {loginError && <div className="auth-error" role="alert">{loginError}</div>}
            <button className="btn-primary" type="submit" disabled={loginLoading}>
              {loginLoading ? 'Signing in…' : 'Sign In'}
            </button>
          </form>
        </div>

        {/* Register Panel */}
        <div className={`auth-panel${tab !== 'register' ? ' hidden' : ''}`}>
          {!googleHidden && (
            <>
              <button className="btn-google" onClick={handleGoogleLogin} type="button">
                <GoogleIcon /> Continue with Google
              </button>
              <div className="auth-divider"><span>or continue with email</span></div>
            </>
          )}
          <form onSubmit={handleRegister} noValidate>
            <div className="form-group">
              <label className="form-label" htmlFor="regEmail">Email</label>
              <input
                className="form-input"
                type="email"
                id="regEmail"
                placeholder="you@example.com"
                value={regEmail}
                onChange={e => setRegEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="regPassword">
                Password <span className="form-hint">min 8 characters</span>
              </label>
              <input
                className="form-input"
                type="password"
                id="regPassword"
                placeholder="••••••••"
                value={regPw}
                onChange={e => setRegPw(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
              />
            </div>
            {regError && <div className="auth-error" role="alert">{regError}</div>}
            <button className="btn-primary" type="submit" disabled={regLoading}>
              {regLoading ? 'Creating…' : 'Create Account'}
            </button>
          </form>
        </div>
      </div>

      {showForgot && (
        <ForgotPasswordModal onClose={() => setShowForgot(false)} showToast={showToast} />
      )}
      {showReset && (
        <ResetPasswordModal
          token={resetTok}
          showToast={showToast}
          onSuccess={() => { setShowReset(false); onLogin() }}
        />
      )}
    </div>
  )
}
