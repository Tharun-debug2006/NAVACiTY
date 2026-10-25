/**
 * The crowd-level indicator.
 *
 * The thresholds mirror the backend (navacity_core/config.py):
 *   Low       0 - 40 %
 *   Moderate 40 - 65 %
 *   High     65 - 85 %
 *   Critical 85 % +
 *
 * A crowd level is **never** carried by colour alone: every badge renders an
 * icon shape (filled circle / half-filled circle / triangle / octagon) *and*
 * the level name as text.
 */

const STYLES = {
  Low: {
    badge: 'bg-crowd-low-soft text-crowd-low ring-crowd-low/20',
    dot: 'bg-crowd-low',
    bar: 'bg-crowd-low',
    hex: '#0f8a5f',
  },
  Moderate: {
    badge: 'bg-crowd-moderate-soft text-crowd-moderate ring-crowd-moderate/20',
    dot: 'bg-crowd-moderate',
    bar: 'bg-crowd-moderate',
    hex: '#0369a1',
  },
  High: {
    badge: 'bg-crowd-high-soft text-crowd-high ring-crowd-high/20',
    dot: 'bg-crowd-high',
    bar: 'bg-crowd-high',
    hex: '#c2410c',
  },
  Critical: {
    badge: 'bg-crowd-critical-soft text-crowd-critical ring-crowd-critical/20',
    dot: 'bg-crowd-critical',
    bar: 'bg-crowd-critical',
    hex: '#b91c1c',
  },
  Unknown: {
    badge: 'bg-slate-100 text-slate-600 ring-slate-200',
    dot: 'bg-slate-400',
    bar: 'bg-slate-400',
    hex: '#94a3b8',
  },
}

export const CROWD_COLORS = Object.fromEntries(
  Object.entries(STYLES).map(([key, value]) => [key, value.hex]),
)

export function crowdColor(level) {
  return (STYLES[level] ?? STYLES.Unknown).hex
}

/** The plain-language sentence that describes what a passenger will feel. */
export const CROWD_SENTENCE = {
  Low: 'There is plenty of room, so you will find a seat.',
  Moderate: 'It is fairly comfortable, but a few people may wait for the next one.',
  High: 'It is crowded and boarding is slow, so expect a short queue.',
  Critical: 'It is overcrowded and some passengers may be left behind.',
  Unknown: 'The crowd level of this service is not known.',
}

/**
 * The icon shape of a crowd level.  The shape carries the meaning, so the
 * badge still works in greyscale or for a colour-blind reader.
 */
function CrowdIcon({ level, className = 'h-3 w-3' }) {
  const style = STYLES[level] ?? STYLES.Unknown
  const common = { className, 'aria-hidden': 'true', focusable: 'false' }

  if (level === 'Low') {
    // Filled circle.
    return (
      <svg viewBox="0 0 12 12" fill="currentColor" {...common}>
        <circle cx="6" cy="6" r="5" />
      </svg>
    )
  }
  if (level === 'Moderate') {
    // Half-filled circle.
    return (
      <svg viewBox="0 0 12 12" {...common}>
        <circle cx="6" cy="6" r="5" fill="none" stroke="currentColor" strokeWidth="2" />
        <path d="M6 1a5 5 0 0 1 0 10z" fill="currentColor" />
      </svg>
    )
  }
  if (level === 'High') {
    // Triangle.
    return (
      <svg viewBox="0 0 12 12" fill="currentColor" {...common}>
        <path d="M6 1 11.5 10.5H0.5z" />
      </svg>
    )
  }
  if (level === 'Critical') {
    // Octagon.
    return (
      <svg viewBox="0 0 12 12" fill="currentColor" {...common}>
        <path d="M4 0.6h4l3.4 3.4v4L8 11.4H4L0.6 8V4z" />
      </svg>
    )
  }
  // Unknown: an empty circle.
  return (
    <svg viewBox="0 0 12 12" {...common}>
      <circle
        cx="6"
        cy="6"
        r="4.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeDasharray="2 1.5"
      />
    </svg>
  )
}

const SIZING = {
  sm: 'px-2 py-0.5 text-[11px]',
  md: 'px-2.5 py-1 text-xs',
  lg: 'px-3 py-1.5 text-sm',
}

export default function CrowdBadge({ level, occupancyPct, size = 'md', className = '' }) {
  const style = STYLES[level] ?? STYLES.Unknown
  const sizing = SIZING[size] ?? SIZING.md
  const showPercent = occupancyPct !== undefined && occupancyPct !== null
  return (
    <span
      className={`badge ${style.badge} ${sizing} ring-1 ring-inset ${className}`}
      title={
        showPercent
          ? `Simulated occupancy ${Number(occupancyPct).toFixed(1)} % of capacity`
          : 'Simulated crowd level'
      }
    >
      <span className={style.dot}>
        <CrowdIcon level={level} className={size === 'lg' ? 'h-3.5 w-3.5' : 'h-3 w-3'} />
      </span>
      <span>{level}</span>
      {showPercent && (
        <span className="tabular-nums opacity-80">
          {Number(occupancyPct).toFixed(0)}%
        </span>
      )}
    </span>
  )
}

/**
 * The occupancy bar with the crowd thresholds marked at 40 %, 65 % and 85 %.
 */
export function OccupancyBar({
  occupancyPct,
  level,
  className = '',
  showThresholds = true,
  label = 'How full the service is',
}) {
  const style = STYLES[level] ?? STYLES.Unknown
  const width = Math.max(0, Math.min(100, Number(occupancyPct) || 0))
  const thresholds = [40, 65, 85]
  return (
    <div className={className}>
      <div
        className="relative h-2.5 w-full overflow-hidden rounded-full bg-slate-200"
        role="progressbar"
        aria-valuenow={Math.round(width)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${label}: ${width.toFixed(1)} % of capacity`}
      >
        <div
          className={`h-full rounded-full ${style.bar} transition-all duration-500`}
          style={{ width: `${width}%` }}
        />
        {showThresholds &&
          thresholds.map((tick) => (
            <span
              key={tick}
              aria-hidden="true"
              className="absolute top-0 h-full w-px bg-white/80"
              style={{ left: `${tick}%` }}
            />
          ))}
      </div>
      {showThresholds && (
        <div
          className="mt-1 flex justify-between text-[10px] tabular-nums text-slate-400"
          aria-hidden="true"
        >
          <span>0 %</span>
          <span>40</span>
          <span>65</span>
          <span>85</span>
          <span>100 %</span>
        </div>
      )}
    </div>
  )
}

export { CrowdIcon }
