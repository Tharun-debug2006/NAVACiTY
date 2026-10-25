/**
 * The one number-formatting helper of the application.
 *
 * Indian grouping is used everywhere (the audience is Bengaluru-based), so
 * 64866540 is written as "6,48,66,540" and 2408 as "2,408".  Every screen
 * imports this file - there is no second implementation.
 */

const INDIAN_GROUPED = new Intl.NumberFormat('en-IN')

/** Format a number with Indian grouping (2,408 / 6,48,66,540). */
export function formatNumber(value, options = {}) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return '0'
  return INDIAN_GROUPED.format(Math.round(numeric))
}

/** Format a number with a fixed number of decimals and Indian grouping. */
export function formatDecimal(value, decimals = 1) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return (0).toFixed(decimals)
  return numeric.toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

/** Format a percentage with a fixed number of decimals. */
export function formatPercent(value, decimals = 1) {
  return `${formatDecimal(value, decimals)} %`
}

/** Format an hour of the day as "08:00". */
export function formatHour(hour) {
  return `${String(hour).padStart(2, '0')}:00`
}

/** Format a number of minutes as "5.7 min". */
export function formatMinutes(value, decimals = 1) {
  return `${formatDecimal(value, decimals)} min`
}

export default formatNumber
