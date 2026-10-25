import { useId, useMemo, useState } from 'react'

/**
 * The "From" / "To" station picker.
 *
 * The list is filtered to the places the chosen route serves, and it can be
 * searched by name.  A swap button exchanges the two ends.
 */
export default function StationPicker({
  originId,
  destinationId,
  stops,
  onOriginChange,
  onDestinationChange,
  onSwap,
  disabled = false,
}) {
  const [query, setQuery] = useState('')
  const originLabelId = useId()
  const destinationLabelId = useId()

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return stops
    return stops.filter((stop) => stop.name.toLowerCase().includes(needle))
  }, [stops, query])

  return (
    <div className="space-y-3">
      <div className="flex items-end gap-2">
        <div className="min-w-0 flex-1">
          <label className="label" htmlFor={`${originLabelId}-origin`}>
            From
          </label>
          <select
            id={`${originLabelId}-origin`}
            className="select"
            value={originId}
            disabled={disabled}
            onChange={(event) => onOriginChange(event.target.value)}
          >
            {stops.map((stop) => (
              <option key={stop.id} value={stop.id}>
                {stop.name}
              </option>
            ))}
          </select>
        </div>

        <button
          type="button"
          onClick={onSwap}
          disabled={disabled}
          aria-label="Swap the origin and the destination"
          title="Swap the origin and the destination"
          className="btn-ghost h-[42px] w-[42px] shrink-0 px-0"
        >
          <svg
            aria-hidden="true"
            className="h-4 w-4"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M7 4v13m0 0l-3-3m3 3l3-3M17 20V7m0 0l-3 3m3-3l3 3"
            />
          </svg>
        </button>

        <div className="min-w-0 flex-1">
          <label className="label" htmlFor={`${destinationLabelId}-destination`}>
            To
          </label>
          <select
            id={`${destinationLabelId}-destination`}
            className="select"
            value={destinationId}
            disabled={disabled}
            onChange={(event) => onDestinationChange(event.target.value)}
          >
            {stops.map((stop) => (
              <option key={stop.id} value={stop.id}>
                {stop.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {stops.length > 6 && (
        <div>
          <label className="sr-only" htmlFor={`${originLabelId}-search`}>
            Search the stations of this route
          </label>
          <input
            id={`${originLabelId}-search`}
            type="search"
            className="select"
            placeholder="Search the stations of this route…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          {query && filtered.length !== stops.length && (
            <p className="mt-1 text-xs text-slate-500" role="status">
              {filtered.length} of {stops.length} stations match “{query}”. Use the
              lists above to pick one.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
