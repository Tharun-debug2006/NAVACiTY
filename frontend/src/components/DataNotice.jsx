/**
 * The simulated-data banner.
 *
 * The same banner is used on every page (public and authority) so that the
 * "this is not real data" message is impossible to miss.
 */
export default function DataNotice({ inline = false, children }) {
  if (inline) {
    return (
      <p className="data-notice-inline" role="note">
        {children || (
          <>
            <strong>Simulated data</strong> for a fictional city. Not real
            timetables or passenger counts.
          </>
        )}
      </p>
    )
  }
  return (
    <div className="data-notice" role="note">
      <strong>Simulated data</strong> — NavaCity is a fictional city. All
      passenger figures, crowd levels and forecasts come from a rule-based
      simulator and a model trained on that simulated data. They are not real
      timetables or passenger counts.
    </div>
  )
}
