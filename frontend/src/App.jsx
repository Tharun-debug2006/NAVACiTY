import { useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import PublicDashboard from './pages/PublicDashboard.jsx'
import AuthorityDashboard from './pages/AuthorityDashboard.jsx'
import AuthorityLogin from './pages/AuthorityLogin.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import { AuthProvider, useAuth } from './context/AuthContext.jsx'
import { api } from './api/client.js'
import { Spinner } from './components/States.jsx'
import DataNotice from './components/DataNotice.jsx'

const NAV_ITEMS = [
  { to: '/public', label: 'Public dashboard', icon: 'M3 12l9-9 9 9M5 10v10h14V10' },
  { to: '/authority', label: 'Authority dashboard', icon: 'M4 19V5m0 14h16M8 15v-4m4 4V8m4 7v-6' },
]

function Shell() {
  const [health, setHealth] = useState({ status: 'checking', record_count: 0 })
  const { isAuthenticated } = useAuth()

  useEffect(() => {
    let active = true
    const load = () => {
      api
        .health()
        .then((data) => active && setHealth(data))
        .catch(() => active && setHealth({ status: 'offline', record_count: 0 }))
    }
    load()
    const timer = setInterval(load, 30000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [])

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-content flex-wrap items-center gap-3 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-card bg-metro-700 text-white">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 19v-6a2 2 0 012-2h4a2 2 0 012 2v6M5 19h14M7 9V7a2 2 0 012-2h6a2 2 0 012 2v2" />
              </svg>
            </div>
            <div>
              <h1 className="text-lg font-semibold leading-tight text-slate-900">NavaCity</h1>
              <p className="text-xs leading-tight text-slate-500">Smart Transport Intelligence</p>
            </div>
          </div>

          <span className="badge bg-amber-50 text-amber-900 ring-1 ring-inset ring-amber-200">
            Simulated data
          </span>

          <nav className="ml-auto flex items-center gap-1 rounded-control bg-slate-100 p-1">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-2 rounded-control px-3 py-1.5 text-sm font-medium transition ${
                    isActive
                      ? 'bg-white text-metro-700 shadow-sm'
                      : 'text-slate-600 hover:text-slate-900'
                  }`
                }
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                  <path strokeLinecap="round" strokeLinejoin="round" d={item.icon} />
                </svg>
                <span className="hidden sm:inline">{item.label}</span>
              </NavLink>
            ))}
          </nav>

          <div className="flex items-center gap-2 text-xs">
            {health.status === 'ok' && (
              <span className="badge bg-crowd-low-soft text-crowd-low ring-1 ring-inset ring-crowd-low/20">
                API online
              </span>
            )}
            {health.status === 'degraded' && (
              <span className="badge bg-amber-50 text-amber-900 ring-1 ring-inset ring-amber-200">
                Degraded
              </span>
            )}
            {health.status === 'offline' && (
              <span className="badge bg-red-50 text-red-700 ring-1 ring-inset ring-red-200">
                API offline
              </span>
            )}
            {health.status === 'checking' && <Spinner className="h-4 w-4 text-slate-400" />}
          </div>
        </div>
      </header>

      <DataNotice />

      <main className="mx-auto max-w-content px-4 py-6 sm:px-6">
        <Routes>
          <Route path="/" element={<Navigate to="/public" replace />} />
          <Route path="/public" element={<PublicDashboard />} />
          <Route path="/authority/login" element={<AuthorityLogin />} />
          <Route
            path="/authority"
            element={
              <ProtectedRoute>
                <AuthorityDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="*"
            element={
              <div className="card text-center text-sm text-slate-600">
                Page not found. Use the navigation above.
              </div>
            }
          />
        </Routes>
      </main>

      <footer className="mt-8 border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-500">
        NavaCity Smart City · VTU B.E. Artificial Intelligence &amp; Machine Learning
        mini-project · built with FastAPI, scikit-learn, React, Tailwind CSS and Recharts ·
        all data is simulated.
      </footer>
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  )
}
