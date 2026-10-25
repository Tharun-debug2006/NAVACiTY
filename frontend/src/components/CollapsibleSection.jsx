import { useState } from 'react'

/**
 * A section that can be folded away.
 *
 * Used for the network map and for the "How crowd levels are defined"
 * explainer, so that the public page stays uncluttered.
 */
export default function CollapsibleSection({
  title,
  subtitle,
  defaultOpen = false,
  children,
  className = '',
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <section className={`card ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 text-left"
      >
        <span>
          <span className="card-title block">{title}</span>
          {subtitle && (
            <span className="mt-0.5 block text-xs text-slate-500">{subtitle}</span>
          )}
        </span>
        <svg
          aria-hidden="true"
          className={`h-4 w-4 shrink-0 text-slate-500 transition-transform ${
            open ? 'rotate-180' : ''
          }`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {open && <div className="mt-4">{children}</div>}
    </section>
  )
}
