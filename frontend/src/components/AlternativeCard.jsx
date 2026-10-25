import CrowdBadge from './CrowdBadge.jsx'

/**
 * One less crowded alternative.
 *
 * The total journey time is the headline: it is the number the passenger
 * compares with the route they already chose.  The comparison with the
 * chosen route is passed in as `differenceMinutes`.
 */
export default function AlternativeCard({
  routeId,
  routeName,
  mode,
  totalMinutes,
  crowdLevel,
  occupancyPct,
  transfers,
  differenceMinutes,
  note,
}) {
  const difference = Number(differenceMinutes)
  const hasDifference = Number.isFinite(difference)
  const slower = hasDifference && difference > 0.05
  const faster = hasDifference && difference < -0.05

  return (
    <li className="rounded-control border border-slate-200 p-3 transition hover:border-metro-200 hover:bg-slate-50">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-900">
            <span className={mode === 'bus' ? 'text-bus-700' : 'text-metro-700'}>
              {routeId}
            </span>
            {' · '}
            {routeName}
          </p>
          <p className="mt-0.5 text-xs text-slate-500">
            {transfers === 0 ? 'Direct, no change' : `${transfers} change`}
          </p>
        </div>
        <CrowdBadge level={crowdLevel} occupancyPct={occupancyPct} size="sm" />
      </div>
      <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-base font-semibold tabular-nums text-slate-900">
          {totalMinutes} min
        </span>
        <span className="text-xs text-slate-500">total journey</span>
        {hasDifference && (
          <span
            className={`text-xs font-medium tabular-nums ${
              faster ? 'text-crowd-low' : slower ? 'text-crowd-high' : 'text-slate-500'
            }`}
          >
            {faster
              ? `${Math.abs(difference).toFixed(0)} min faster than your route`
              : slower
                ? `${difference.toFixed(0)} min slower than your route`
                : 'same time as your route'}
          </span>
        )}
      </div>
      {note && <p className="mt-1 text-[11px] leading-snug text-slate-500">{note}</p>}
    </li>
  )
}
