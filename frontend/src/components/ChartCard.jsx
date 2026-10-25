/**
 * A chart with a title, a legend area and a caption.
 *
 * Every chart of the application uses this wrapper, which guarantees that
 * each one has a title, a visible legend, axis units inside the plot and a
 * caption that states the data period and the granularity.
 */
export default function ChartCard({
  title,
  subtitle,
  legend,
  caption,
  children,
  className = '',
  bodyClassName = '',
}) {
  return (
    <section className={`card ${className}`} aria-label={title}>
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="card-title">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
        </div>
        {legend && <div className="flex flex-wrap items-center gap-3">{legend}</div>}
      </div>
      <div className={bodyClassName}>{children}</div>
      {caption && (
        <p className="mt-3 border-t border-slate-100 pt-2 text-[11px] leading-snug text-slate-500">
          {caption}
        </p>
      )}
    </section>
  )
}

/** One entry of a chart legend (a coloured line plus its name). */
export function LegendItem({ color, label, dashed = false, className = '' }) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs text-slate-600 ${className}`}>
      <span
        aria-hidden="true"
        className="inline-block h-0.5 w-4 rounded-full"
        style={{
          backgroundColor: dashed
            ? `repeating-linear-gradient(90deg, ${color} 0 4px, transparent 4px 7px)`
            : color,
        }}
      />
      {label}
    </span>
  )
}
