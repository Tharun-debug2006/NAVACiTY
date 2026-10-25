/** Reusable loading, empty and error states. */

/**
 * A skeleton that has the shape of the content it replaces - never a spinner
 * in the middle of an empty page.
 */
export function LoadingSkeleton({ label = 'Loading…', rows = 3, className = '' }) {
  return (
    <div className={`space-y-3 ${className}`} role="status" aria-live="polite">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }).map((_, index) => (
        <div
          key={index}
          aria-hidden="true"
          className={`skeleton ${index === 0 ? 'h-6 w-2/5' : 'h-12 w-full'}`}
        />
      ))}
    </div>
  )
}

/** The older alias, kept so that existing imports keep working. */
export const LoadingState = LoadingSkeleton

export function ErrorState({ message, onRetry, title = 'Something went wrong' }) {
  return (
    <div
      className="rounded-card border border-red-200 bg-red-50 p-5 text-sm text-red-800"
      role="alert"
    >
      <p className="font-semibold">{title}</p>
      <p className="mt-1 break-words">{message}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="btn-ghost btn-sm mt-3">
          Try again
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title = 'No data', message, action }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-card border border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center">
      <svg
        className="h-8 w-8 text-slate-400"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={1.5}
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z"
        />
      </svg>
      <p className="mt-3 text-sm font-semibold text-slate-700">{title}</p>
      {message && <p className="mt-1 max-w-md text-sm text-slate-500">{message}</p>}
      {action}
    </div>
  )
}

export function Spinner({ className = 'h-4 w-4' }) {
  return (
    <svg
      className={`${className} animate-spin text-current`}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  )
}
