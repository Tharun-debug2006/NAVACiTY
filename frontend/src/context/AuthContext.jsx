import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import {
  api,
  clearAuthToken,
  errorMessage,
  isAuthUnavailable,
  isUnauthorized,
  setAuthToken,
} from '../api/client.js'

/**
 * The authority authentication state of the React application.
 *
 * The session token is held in memory only (see api/client.js) and is
 * validated by the backend on every request.  The context exposes the
 * sign-in / sign-out actions and the state the UI needs to render the login
 * screen, the protected route and the "session expired" handling.
 */
const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [status, setStatus] = useState('anonymous') // anonymous | checking | authenticated
  const [session, setSession] = useState(null)
  const [config, setConfig] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  // ---- Read the public description of the auth setup ------------------
  const loadConfig = useCallback(async () => {
    try {
      const data = await api.authConfig()
      setConfig(data)
      return data
    } catch (err) {
      setConfig(null)
      return null
    }
  }, [])

  // ---- Sign in ---------------------------------------------------------
  const signIn = useCallback(
    async (password) => {
      setBusy(true)
      setError(null)
      try {
        const data = await api.login(password)
        setAuthToken(data.access_token)
        setSession(data.session)
        setStatus('authenticated')
        return { ok: true, data }
      } catch (err) {
        const message = isAuthUnavailable(err)
          ? 'The authority authentication is not configured on the server. Set NAVACITY_AUTH_PASSWORD and restart the backend.'
          : isUnauthorized(err)
            ? 'That password is not correct.'
            : errorMessage(err)
        setError(message)
        setStatus('anonymous')
        return { ok: false, error: message }
      } finally {
        setBusy(false)
      }
    },
    [],
  )

  // ---- Sign out --------------------------------------------------------
  const signOut = useCallback(async () => {
    setBusy(true)
    try {
      await api.logout()
    } catch {
      // The token may already be invalid; the local state is cleared anyway.
    } finally {
      clearAuthToken()
      setSession(null)
      setStatus('anonymous')
      setBusy(false)
    }
  }, [])

  // ---- The session was rejected by the server --------------------------
  const handleUnauthorized = useCallback(() => {
    clearAuthToken()
    setSession(null)
    setStatus('anonymous')
  }, [])

  // ---- Restore a session that is still valid on the server ------------
  const restore = useCallback(async () => {
    setStatus('checking')
    await loadConfig()
    try {
      const data = await api.session()
      setSession(data)
      setStatus('authenticated')
      return true
    } catch (err) {
      if (!isUnauthorized(err)) {
        // The backend is unreachable: the public part still works.
        setStatus('anonymous')
        return false
      }
      handleUnauthorized()
      return false
    }
  }, [handleUnauthorized, loadConfig])

  const value = useMemo(
    () => ({
      status,
      isAuthenticated: status === 'authenticated',
      isChecking: status === 'checking',
      session,
      config,
      error,
      busy,
      signIn,
      signOut,
      handleUnauthorized,
      loadConfig,
      restore,
    }),
    [status, session, config, error, busy, signIn, signOut, handleUnauthorized, loadConfig, restore],
  )

  // On mount: read the public auth configuration and try to restore a session
  // that the backend still accepts.
  useEffect(() => {
    restore()
  }, [restore])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

/**
 * Read the authority authentication state.
 */
export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used inside an <AuthProvider>.')
  }
  return context
}

export default AuthContext
