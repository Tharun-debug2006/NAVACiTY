import axios from 'axios'

// The Vite dev server proxies /api to the FastAPI backend (see vite.config.js),
// so the same relative URL works in development and in a production build that
// is served behind the same reverse proxy.
const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

// --------------------------------------------------------------------------
// The authority session token
//
// The token is kept in memory only.  It is deliberately NOT written to
// localStorage or sessionStorage: a token in web storage survives a browser
// restart and is readable by any script that runs on the page, which is
// exactly what the backend-enforced authentication is meant to prevent.
//
// The user has to sign in again after a page reload.  That is the price of
// not persisting a credential in the browser.
// --------------------------------------------------------------------------
let authToken = null

export function setAuthToken(token) {
  authToken = token || null
}

export function getAuthToken() {
  return authToken
}

export function clearAuthToken() {
  authToken = null
}

/** True when a session token is currently held in memory. */
export function hasAuthToken() {
  return Boolean(authToken)
}

const client = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

/**
 * Attach the session token to every request that carries one.
 */
client.interceptors.request.use((config) => {
  if (authToken) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${authToken}`
  }
  return config
})

/**
 * Turn an axios failure into a readable message.
 */
export function errorMessage(error) {
  if (!error) return 'Unknown error'
  if (error.response) {
    const { status, data } = error.response
    const detail = data?.detail
    if (typeof detail === 'string') return `HTTP ${status}: ${detail}`
    if (Array.isArray(detail) && detail.length > 0) {
      return `HTTP ${status}: ${detail
        .map((item) => `${item.loc?.slice(-1)[0] ?? 'input'} ${item.msg}`)
        .join('; ')}`
    }
    return `HTTP ${status}: the request could not be processed.`
  }
  if (error.code === 'ECONNABORTED') {
    return 'The request timed out. Is the backend running on port 8000?'
  }
  return 'Cannot reach the NavaCity API. Is the backend running on port 8000?'
}

/** True when the failure is an "authentication required" answer. */
export function isUnauthorized(error) {
  return Boolean(error?.response?.status === 401)
}

/** True when the failure is a "misconfigured server" answer. */
export function isAuthUnavailable(error) {
  return Boolean(error?.response?.status === 503)
}

const get = async (url, params) => {
  const response = await client.get(url, { params })
  return response.data
}

const post = async (url, body) => {
  const response = await client.post(url, body)
  return response.data
}

export const api = {
  health: () => get('/health'),
  network: () => get('/network'),
  routes: (mode) => get('/routes', { mode }),
  places: (params) => get('/places', params),
  events: () => get('/events'),
  crowdLevels: () => get('/crowd-levels'),
  history: (params) => get('/history', params),
  hourlyProfile: (params) => get('/history/hourly', params),
  predict: (payload) => post('/predict', payload),
  predictDay: (params) => get('/predict/day', params),
  alternatives: (params) => get('/alternatives', params),
  // --- Authority only (a session token is required) ---
  authConfig: () => get('/auth/config'),
  login: (password) => post('/auth/login', { password }),
  logout: () => post('/auth/logout'),
  session: () => get('/auth/session'),
  authorityStats: (params) => get('/authority/stats', params),
  modeSummary: () => get('/authority/mode-summary'),
  recommendations: (params) => get('/authority/recommendations', params),
  crowdSummary: (params) => get('/crowd-summary', params),
  alerts: (params) => get('/alerts', params),
  modelMetrics: () => get('/model/metrics'),
}

export default api
