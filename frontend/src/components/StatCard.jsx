/**
 * A KPI card for the authority dashboard.
 *
 * The value is rendered with `tabular-nums` so that a row of cards aligns.
 */
export default function StatCard({ label, value, unit, detail, context, className = '' }) {
  return (
    <div className={`card-compact ${className}`}>
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="mt-1 stat-value">
        {value}
        {unit && <span className="ml-1 text-sm font-normal text-slate-500">{unit}</span>}
      </p>
      {detail && <p className="mt-1 text-[11px] leading-snug text-slate-500">{detail}</p>}
      {context && <p className="mt-1 text-[11px] leading-snug text-slate-400">{context}</p>}
    </div>
  )
}
