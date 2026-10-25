import { useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { Spinner } from '../components/States.jsx'

/**
 * The sign-in screen of the transport-authority dashboard.
 *
 * The password is sent to the backend over the API; the backend verifies it
 * and answers with a short-lived session token.  The token is kept in memory
 * only - it is never written to localStorage or sessionStorage.
 */
export default function AuthorityLogin() {
  const { signIn, signOut, isAuthenticated, isChecking, config, error, busy } = useAuth()
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const navigate = useNavigate()

  // Load the public description of the authentication setup.
  useEffect(() => {
    // The provider already tried to restore a session; nothing else to do
    // here beyond keeping the form in a clean state.
  }, [])

  if (isChecking) {
    return (
      <div className="card flex min-h-[320px] items-center justify-center">
        <Spinner className="h-6 w-6 text-navy-600" />
        <span className="ml-3 text-sm text-slate-500">Checking the session…</span>
      </div>
    )
  }

  if (isAuthenticated) {
    return <Navigate to="/authority" replace />
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (!password || busy) return
    const result = await signIn(password)
    if (result.ok) {
      setPassword('')
      navigate('/authority', { replace: true })
    }
  }

  const demoMode = config?.demo_mode === true
  const notConfigured = config && config.configured === false

  return (
    <div className="mx-auto max-w-md">
      <div className="card">
        <div className="flex items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-card bg-metro-700 text-white">
            <svg
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.8}
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
              />
            </svg>
          </div>
          <div>
            <h1 className="text-lg font-semibold text-slate-900">Transport authority sign-in</h1>
            <p className="mt-0.5 text-xs text-slate-500">
              The authority statistics, alerts and recommendations are protected by the
              backend.
            </p>
          </div>
        </div>

        {notConfigured && (
          <div
            className="mt-4 rounded-control border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900"
            role="alert"
          >
            <p className="font-semibold">Authentication is not configured</p>
            <p className="mt-1">
              {config?.error ||
                'Set NAVACITY_AUTH_PASSWORD on the server and restart it.'}
            </p>
          </div>
        )}

        {demoMode && (
          <div className="mt-4 rounded-control border border-metro-200 bg-metro-50 p-3 text-xs text-metro-800">
            <p className="font-semibold">Local demo mode</p>
            <p className="mt-1">
              The server accepts the well-known local demo password, which is
              documented in the README. Never use this mode in a real deployment.
            </p>
          </div>
        )}

        <form className="mt-5 space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="label" htmlFor="authority-password">
              Authority password
            </label>
            <div className="relative">
              <input
                id="authority-password"
                type={showPassword ? 'text' : 'password'}
                className="select pr-20"
                value={password}
                autoComplete="current-password"
                autoFocus
                disabled={busy || notConfigured}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter the transport-authority password"
              />
              <button
                type="button"
                onClick={() => setShowPassword((value) => !value)}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded px-2 py-1 text-xs font-semibold text-slate-500 hover:text-slate-800"
              >
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </div>
          </div>

          {error && (
            <p
              className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800"
              role="alert"
            >
              {error}
            </p>
          )}

          <button
            type="submit"
            className="btn-primary w-full"
            disabled={busy || !password || notConfigured}
          >
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <div className="mt-5 border-t border-slate-100 pt-4">
          <p className="text-[11px] leading-relaxed text-slate-500">
            The password is verified by the FastAPI backend and is never stored in the
            browser. The session token is kept in memory only, expires after{' '}
            {config?.session_minutes ?? 60} minutes and is rejected by the server as soon
            as you sign out.
          </p>
          <button
            type="button"
            className="btn-ghost mt-3 w-full"
            onClick={signOut}
            disabled={busy}
          >
            Back to the public dashboard
          </button>
        </div>
      </div>
    </div>
  )
}
