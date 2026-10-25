import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { Spinner } from './States.jsx'

/**
 * A route that requires a signed-in transport authority.
 *
 * The check is a convenience for the user interface; the real protection is
 * enforced by the backend, which answers `401` for every authority request
 * that does not carry a valid session token.
 */
export default function ProtectedRoute({ children }) {
  const { isAuthenticated, isChecking } = useAuth()
  const location = useLocation()

  if (isChecking) {
    return (
      <div className="card flex min-h-[240px] items-center justify-center">
        <Spinner className="h-6 w-6 text-navy-600" />
        <span className="ml-3 text-sm text-slate-500">
          Checking the authority session…
        </span>
      </div>
    )
  }

  if (!isAuthenticated) {
    // Remember where the user wanted to go, so the sign-in can return there.
    return <Navigate to="/authority/login" replace state={{ from: location.pathname }} />
  }

  return children
}
