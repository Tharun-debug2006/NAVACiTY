import CrowdBadge, { OccupancyBar } from './CrowdBadge.jsx'

/**
 * The single primary answer of the public interface.
 *
 * A passenger should be able to read this one card and know whether the trip
 * is crowded and how long they will wait.  The crowd level is shown as a
 * badge with an icon shape *and* a text label, never as colour alone.
 */
export default function AnswerCard({
  crowdLevel,
  occupancyPct,
  headline,
  sentence,
  waitMinutes,
  rideMinutes,
  totalMinutes,
  children,
}) {
  return (
    <section className="card border-l-4 border-l-metro-700" aria-label="Your journey">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="card-title">Your journey</p>
          <p className="mt-1 text-lg font-semibold text-slate-900">{headline}</p>
          {sentence && <p className="mt-1 text-sm text-slate-600">{sentence}</p>}
        </div>
        <CrowdBadge level={crowdLevel} occupancyPct={occupancyPct} size="lg" />
      </div>

      <dl className="mt-4 grid grid-cols-3 gap-3 border-y border-slate-100 py-3">
        <div>
          <dt className="text-xs text-slate-500">Expected wait</dt>
          <dd className="mt-0.5 text-xl font-semibold tabular-nums text-slate-900">
            {waitMinutes}
            <span className="ml-1 text-sm font-normal text-slate-500">min</span>
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Ride time</dt>
          <dd className="mt-0.5 text-xl font-semibold tabular-nums text-slate-900">
            {rideMinutes}
            <span className="ml-1 text-sm font-normal text-slate-500">min</span>
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Total journey</dt>
          <dd className="mt-0.5 text-xl font-semibold tabular-nums text-slate-900">
            {totalMinutes}
            <span className="ml-1 text-sm font-normal text-slate-500">min</span>
          </dd>
        </div>
      </dl>

      <div className="mt-3">
        <OccupancyBar occupancyPct={occupancyPct} level={crowdLevel} />
      </div>
      {children}
    </section>
  )
}
