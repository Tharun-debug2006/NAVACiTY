import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api, errorMessage } from '../api/client.js'
import { CROWD_COLORS, CROWD_SENTENCE, OccupancyBar } from '../components/CrowdBadge.jsx'
import TransitMap from '../components/TransitMap.jsx'
import ModeSwitch from '../components/ModeSwitch.jsx'
import StationPicker from '../components/StationPicker.jsx'
import AnswerCard from '../components/AnswerCard.jsx'
import AlternativeCard from '../components/AlternativeCard.jsx'
import CollapsibleSection from '../components/CollapsibleSection.jsx'
import ChartCard, { LegendItem } from '../components/ChartCard.jsx'
import DataNotice from '../components/DataNotice.jsx'
import { EmptyState, ErrorState, LoadingSkeleton } from '../components/States.jsx'
import { formatDecimal, formatHour, formatNumber } from '../lib/format.js'

const HOURS = Array.from({ length: 24 }, (_, i) => i)

// The window the model was trained on.  The date picker is limited to it and
// the forecast card warns when a date outside it is used.
const SUPPORTED_START = '2025-01-01'
const SUPPORTED_END = '2025-06-30'

/** A typical weekday inside the supported window. */
function typicalWeekdayISO() {
  // 2025-06-30 is a Monday and the last day of the simulated period.
  return '2025-06-30'
}

function isWithinSupportedRange(value) {
  return value >= SUPPORTED_START && value <= SUPPORTED_END
}

export default function PublicDashboard() {
  // ---- Static network -------------------------------------------------
  const [network, setNetwork] = useState(null)
  const [networkError, setNetworkError] = useState(null)

  // ---- User selection --------------------------------------------------
  const [mode, setMode] = useState('metro')
  const [routeId, setRouteId] = useState('M1')
  const [hour, setHour] = useState(8)
  const [date, setDate] = useState(typicalWeekdayISO())
  const [isTypicalWeekday, setIsTypicalWeekday] = useState(true)

  // The origin and the destination of the journey.  They are filtered to the
  // stations the chosen route serves and they really determine the forecast.
  const [originId, setOriginId] = useState('')
  const [destinationId, setDestinationId] = useState('')

  // The controls collapse into a summary bar once a result exists.
  const [controlsOpen, setControlsOpen] = useState(false)

  // ---- Server data -----------------------------------------------------
  const [prediction, setPrediction] = useState(null)
  const [predictionError, setPredictionError] = useState(null)
  const [predictionLoading, setPredictionLoading] = useState(false)

  const [dayProfile, setDayProfile] = useState(null)
  const [historyProfile, setHistoryProfile] = useState(null)
  const [alternatives, setAlternatives] = useState(null)
  const [alternativesError, setAlternativesError] = useState(null)
  const [loadingExtras, setLoadingExtras] = useState(false)

  // ---- Load the network once ------------------------------------------
  const loadNetwork = useCallback(async () => {
    try {
      setNetworkError(null)
      const data = await api.network()
      setNetwork(data)
    } catch (error) {
      setNetworkError(errorMessage(error))
    }
  }, [])

  useEffect(() => {
    loadNetwork()
  }, [loadNetwork])

  // ---- Keep the route selection valid for the chosen mode --------------
  const routes = useMemo(() => {
    if (!network) return []
    return mode === 'metro' ? network.metro_lines : network.bus_routes
  }, [network, mode])

  // Switching the mode resets the route list to that mode only.
  const handleModeChange = useCallback((nextMode) => {
    setMode(nextMode)
    if (network) {
      const nextRoutes = nextMode === 'metro' ? network.metro_lines : network.bus_routes
      if (nextRoutes.length && !nextRoutes.some((item) => item.id === routeId)) {
        setRouteId(nextRoutes[0].id)
      }
    }
  }, [network, routeId])

  useEffect(() => {
    if (!routes.length) return
    if (!routes.some((item) => item.id === routeId)) {
      setRouteId(routes[0].id)
    }
  }, [routes, routeId])

  const route = useMemo(
    () => routes.find((item) => item.id === routeId) || null,
    [routes, routeId],
  )

  // The stops of the selected route, as {id, name} pairs for the selects.
  const routeStops = useMemo(() => {
    if (!route) return []
    const names = route.stop_names || []
    return route.stops.map((id, index) => ({
      id,
      name: names[index] || id,
    }))
  }, [route])

  // Keep the origin / the destination valid for the selected route.
  useEffect(() => {
    if (!routeStops.length) return
    if (!routeStops.some((stop) => stop.id === originId)) {
      setOriginId(routeStops[0].id)
    }
    if (!routeStops.some((stop) => stop.id === destinationId)) {
      setDestinationId(routeStops[routeStops.length - 1].id)
    }
  }, [routeStops, originId, destinationId])

  // ---- Prediction ------------------------------------------------------
  // The prediction is driven by the *selected route* and by the journey
  // (origin and destination), so switching the mode never sends a request
  // with a route that belongs to the other mode.
  const loadPrediction = useCallback(async () => {
    if (!route) {
      setPrediction(null)
      setPredictionError(null)
      setPredictionLoading(false)
      return
    }
    setPredictionLoading(true)
    setPredictionError(null)
    try {
      const data = await api.predict({
        route_id: route.id,
        hour: Number(hour),
        date,
        mode: route.mode,
        origin_id: originId || undefined,
        destination_id: destinationId || undefined,
      })
      setPrediction(data)
    } catch (error) {
      setPredictionError(errorMessage(error))
      setPrediction(null)
    } finally {
      setPredictionLoading(false)
    }
  }, [route, hour, date, originId, destinationId])

  useEffect(() => {
    loadPrediction()
  }, [loadPrediction])

  // ---- Day profile + historical profile + alternatives -----------------
  const activeRouteId = route?.id || null

  useEffect(() => {
    if (!activeRouteId || !route) return undefined
    let active = true
    setLoadingExtras(true)
    setAlternativesError(null)

    api
      .predictDay({
        route_id: activeRouteId,
        date,
        origin_id: originId || undefined,
        destination_id: destinationId || undefined,
      })
      .then((data) => active && setDayProfile(data.predictions))
      .catch(() => active && setDayProfile(null))

    api
      .hourlyProfile({ route_id: activeRouteId })
      .then((data) => active && setHistoryProfile(data.points))
      .catch(() => active && setHistoryProfile(null))

    if (route.stops?.length >= 2 && originId && destinationId) {
      api
        .alternatives({
          route_id: activeRouteId,
          origin_id: originId,
          destination_id: destinationId,
          hour: Number(hour),
          date,
          limit: 4,
        })
        .then((data) => active && setAlternatives(data))
        .catch((error) => {
          if (active) {
            setAlternatives(null)
            setAlternativesError(errorMessage(error))
          }
        })
    } else {
      setAlternatives(null)
    }

    return () => {
      active = false
      setLoadingExtras(false)
    }
  }, [activeRouteId, hour, date, route, originId, destinationId])

  // ---- Chart data ------------------------------------------------------
  // The 24-hour chart of the chosen route and day.  The unit is passengers
  // per hour on the busiest stretch of the selected journey.
  const demandChart = useMemo(() => {
    if (!dayProfile) return []
    return dayProfile.map((point) => ({
      hour: point.hour,
      label: formatHour(point.hour),
      passengers: point.predicted_passengers,
      occupancy: point.predicted_occupancy_pct,
      crowd: point.crowd_level,
    }))
  }, [dayProfile])

  const originName = useMemo(
    () => routeStops.find((stop) => stop.id === originId)?.name || '',
    [routeStops, originId],
  )
  const destinationName = useMemo(
    () => routeStops.find((stop) => stop.id === destinationId)?.name || '',
    [routeStops, destinationId],
  )

  const isExtrapolation = prediction?.is_extrapolation === true
  const dateOutOfRange = !isWithinSupportedRange(date)

  // The one-sentence answer a passenger reads first.
  const answerSentence = useMemo(() => {
    if (!prediction) return ''
    const level = prediction.crowd_level
    const base = CROWD_SENTENCE[level] || ''
    if (level === 'Low') {
      return `Expect a quiet service at ${formatHour(prediction.hour)}. ${base}`
    }
    if (level === 'Moderate') {
      return `Expect a moderately crowded service at ${formatHour(prediction.hour)}. ${base}`
    }
    if (level === 'High') {
      return `Expect a crowded service at ${formatHour(prediction.hour)}. ${base}`
    }
    if (level === 'Critical') {
      return `Expect a very crowded service at ${formatHour(prediction.hour)}. ${base}`
    }
    return base
  }, [prediction])

  const requestedTotal = alternatives?.requested_total_journey_time_min

  // ---- Render ----------------------------------------------------------
  if (networkError) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-slate-900">Plan a journey</h1>
        <ErrorState
          title="The NavaCity API is not reachable"
          message={networkError}
          onRetry={loadNetwork}
        />
        <div className="card text-sm text-slate-600">
          <p className="font-semibold text-slate-800">How to fix this</p>
          <ol className="mt-2 list-decimal space-y-1 pl-5">
            <li>
              Open a terminal in <code className="rounded bg-slate-100 px-1">c:\AI\NavaCity</code>
            </li>
            <li>
              Run{' '}
              <code className="rounded bg-slate-100 px-1">
                python -m uvicorn backend.app.main:app --port 8000
              </code>
            </li>
            <li>
              Check{' '}
              <code className="rounded bg-slate-100 px-1">http://localhost:8000/api/health</code>
            </li>
          </ol>
        </div>
      </div>
    )
  }

  if (!network) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-slate-900">Plan a journey</h1>
        <div className="card">
          <LoadingSkeleton label="Loading the NavaCity network…" rows={4} />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* ================= The answer comes first ================= */}
      {predictionError && (
        <ErrorState message={predictionError} onRetry={loadPrediction} />
      )}

      {predictionLoading && !prediction && (
        <div className="card">
          <LoadingSkeleton label="Working out the crowd level…" rows={3} />
        </div>
      )}

      {prediction && (
        <AnswerCard
          crowdLevel={prediction.crowd_level}
          occupancyPct={prediction.predicted_occupancy_pct}
          headline={`${route.id} · ${route.name} — ${originName} to ${destinationName}`}
          sentence={answerSentence}
          waitMinutes={formatDecimal(prediction.waiting_time_min, 1)}
          rideMinutes={formatDecimal(prediction.travel_time_min, 0)}
          totalMinutes={formatDecimal(prediction.total_journey_time_min, 0)}
        >
          {isExtrapolation && (
            <p className="mt-3 rounded-control border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900" role="note">
              {prediction.extrapolation_notice ||
                'This date is outside the simulated period, so the forecast is an extrapolation.'}{' '}
              The simulated data covers {SUPPORTED_START} to {SUPPORTED_END}.
            </p>
          )}
          {dateOutOfRange && !isExtrapolation && (
            <p className="mt-3 rounded-control border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900" role="note">
              This date is outside the supported range ({SUPPORTED_START} to{' '}
              {SUPPORTED_END}), so the forecast is an extrapolation.
            </p>
          )}
          <p className="mt-3 text-[11px] leading-snug text-slate-500">
            {formatNumber(prediction.predicted_passengers)} passengers per hour
            on the busiest stretch of this journey, which is{' '}
            {formatDecimal(prediction.predicted_occupancy_pct, 1)} % of the
            capacity offered by the planned service (
            {prediction.service_frequency} vehicles per hour ×{' '}
            {prediction.vehicle_capacity} seats = {formatNumber(prediction.hourly_capacity)}{' '}
            places).
          </p>
        </AnswerCard>
      )}

      {/* ================= Controls ================= */}
      <section className="card" aria-label="Journey details">
        {prediction && !controlsOpen ? (
          <button
            type="button"
            onClick={() => setControlsOpen(true)}
            className="flex w-full items-center justify-between gap-3 text-left"
            aria-expanded={false}
          >
            <span className="text-sm text-slate-700">
              <span className="font-semibold">
                {mode === 'metro' ? 'Metro' : 'Bus'} · {routeId} {route.name}
              </span>
              {' · '}
              {isTypicalWeekday ? 'Typical weekday' : date} · {formatHour(hour)}
            </span>
            <span className="shrink-0 text-sm font-semibold text-metro-700">Change</span>
          </button>
        ) : (
          <>
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-base font-semibold text-slate-900">
                Plan your journey
              </h2>
              {prediction && (
                <button
                  type="button"
                  onClick={() => setControlsOpen(false)}
                  className="text-sm font-semibold text-metro-700"
                >
                  Done
                </button>
              )}
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              {/* 1. Mode */}
              <div>
                <span className="label" id="mode-label">
                  Travel mode
                </span>
                <ModeSwitch
                  value={mode}
                  onChange={handleModeChange}
                  id="public-mode-switch"
                />
              </div>

              {/* 2. Route */}
              <div>
                <label className="label" htmlFor="route-select">
                  {mode === 'metro' ? 'Metro line' : 'Bus route'}
                </label>
                <select
                  id="route-select"
                  className="select"
                  value={routeId}
                  onChange={(event) => setRouteId(event.target.value)}
                >
                  {routes.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.id} · {item.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* 3. Journey */}
            <div className="mt-4 border-t border-slate-100 pt-4">
              <p className="label">Your journey</p>
              <StationPicker
                originId={originId}
                destinationId={destinationId}
                stops={routeStops}
                onOriginChange={setOriginId}
                onDestinationChange={setDestinationId}
                onSwap={() => {
                  setOriginId(destinationId)
                  setDestinationId(originId)
                }}
              />
              <p className="mt-2 text-[11px] leading-snug text-slate-500">
                Only the {routeStops.length} stations and stops served by{' '}
                {route.id} are listed. The forecast is made for the busiest
                stretch of the journey you choose.
              </p>
            </div>

            {/* 4. Time */}
            <div className="mt-4 border-t border-slate-100 pt-4">
              <p className="label">When are you travelling?</p>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="label" htmlFor="hour-select">
                    Leave at
                  </label>
                  <select
                    id="hour-select"
                    className="select"
                    value={hour}
                    onChange={(event) => setHour(Number(event.target.value))}
                  >
                    {HOURS.map((value) => (
                      <option key={value} value={value}>
                        {formatHour(value)}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label" htmlFor="date-input">
                    Date
                  </label>
                  <input
                    id="date-input"
                    type="date"
                    className="select"
                    value={date}
                    min={SUPPORTED_START}
                    max={SUPPORTED_END}
                    onChange={(event) => {
                      setDate(event.target.value)
                      setIsTypicalWeekday(false)
                    }}
                  />
                </div>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setDate(typicalWeekdayISO())
                    setIsTypicalWeekday(true)
                  }}
                  aria-pressed={isTypicalWeekday}
                  className={`btn btn-sm ${
                    isTypicalWeekday
                      ? 'bg-metro-700 text-white'
                      : 'border border-slate-300 bg-white text-slate-700'
                  }`}
                >
                  Typical weekday
                </button>
                <span className="text-[11px] text-slate-500">
                  The simulated data covers {SUPPORTED_START} to {SUPPORTED_END}.
                  Dates outside that window are extrapolations.
                </span>
              </div>
            </div>
          </>
        )}
      </section>

      {/* ================= Less crowded alternatives ================= */}
      {prediction && (
        <section className="card" aria-label="Less crowded alternatives">
          <h2 className="card-title">Less crowded alternatives</h2>
          <p className="mt-1 text-xs text-slate-500">
            {alternatives
              ? `Other ways to travel from ${alternatives.origin} to ${alternatives.destination} at ${formatHour(hour)} on ${date}.`
              : `Looking for other ways to travel from ${originName} to ${destinationName}…`}
          </p>

          {alternativesError && (
            <p className="mt-3 rounded-control border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900" role="status">
              {alternativesError}
            </p>
          )}

          {!alternatives && !alternativesError && (
            <div className="mt-3">
              <LoadingSkeleton label="Looking for alternatives…" rows={2} />
            </div>
          )}

          {alternatives && alternatives.alternatives.length === 0 && (
            <div className="mt-3">
              <EmptyState
                title="No alternative found"
                message="The simulated network does not offer another route for this journey."
              />
            </div>
          )}

          {alternatives && alternatives.alternatives.length > 0 && (
            <>
              {requestedTotal !== null && requestedTotal !== undefined && (
                <p className="mt-2 text-xs text-slate-600">
                  Your route {alternatives.requested_route} takes{' '}
                  <strong className="tabular-nums">{formatDecimal(requestedTotal, 0)} min</strong>{' '}
                  in total. Each option below is compared with that time.
                </p>
              )}
              <ul className="mt-3 space-y-2">
                {alternatives.alternatives.map((item) => (
                  <AlternativeCard
                    key={`${item.route_id}-${item.transfers}-${item.segment_id}`}
                    routeId={item.route_id}
                    routeName={item.route_name}
                    mode={item.mode}
                    totalMinutes={formatDecimal(item.total_journey_time_min, 0)}
                    crowdLevel={item.crowd_level}
                    occupancyPct={item.predicted_occupancy_pct}
                    transfers={item.transfers}
                    differenceMinutes={
                      requestedTotal === null || requestedTotal === undefined
                        ? null
                        : item.total_journey_time_min - requestedTotal
                    }
                    note={item.reason}
                  />
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      {/* ================= The 24-hour chart ================= */}
      {prediction && (
        <ChartCard
          title="Expected crowd by hour"
          subtitle={`${route.id} · ${route.name} · ${date}`}
          legend={
            <>
              <LegendItem color={CROWD_COLORS.Low} label="Low" />
              <LegendItem color={CROWD_COLORS.Moderate} label="Moderate" />
              <LegendItem color={CROWD_COLORS.High} label="High" />
              <LegendItem color={CROWD_COLORS.Critical} label="Critical" />
            </>
          }
          caption={`Expected passengers per hour on the busiest stretch of the
            journey, for every hour of the day. The chosen hour is marked with a
            vertical line. The bar colour is the crowd level of that hour. Data
            period: ${SUPPORTED_START} to ${SUPPORTED_END} (simulated).`}
        >
          {!demandChart.length ? (
            <LoadingSkeleton label="Loading the hourly forecast…" rows={3} />
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={demandChart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 11, fill: '#64748b' }}
                  interval={1}
                  label={{
                    value: 'Hour of day',
                    position: 'insideBottom',
                    offset: -2,
                    fontSize: 11,
                    fill: '#64748b',
                  }}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: '#64748b' }}
                  width={56}
                  label={{
                    value: 'Passengers per hour',
                    angle: -90,
                    position: 'insideLeft',
                    fontSize: 11,
                    fill: '#64748b',
                  }}
                />
                <Tooltip
                  formatter={(value, name, item) => [
                    `${formatNumber(value)} passengers per hour`,
                    item?.payload?.crowd ?? 'crowd level',
                  ]}
                  contentStyle={{ fontSize: 12, borderRadius: 8 }}
                />
                <ReferenceLine
                  x={formatHour(hour)}
                  stroke="#1d3fbf"
                  strokeWidth={2}
                  label={{ value: 'Your hour', fontSize: 11, fill: '#1d3fbf', position: 'top' }}
                />
                <Bar dataKey="passengers" radius={[4, 4, 0, 0]}>
                  {demandChart.map((entry) => (
                    <Cell key={entry.hour} fill={CROWD_COLORS[entry.crowd] || '#94a3b8'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      )}

      {/* ================= The network map ================= */}
      {network && (
        <CollapsibleSection
          title="Network map"
          subtitle={`${network.metro_lines.length} metro lines · ${network.bus_routes.length} bus routes · ${network.places.length} stations and stops`}
        >
          <div className="h-[420px] w-full">
            <TransitMap
              network={network}
              selectedRouteId={routeId}
              onSelectRoute={(id, selectedMode) => {
                handleModeChange(selectedMode)
                setRouteId(id)
              }}
            />
          </div>
        </CollapsibleSection>
      )}

      {/* ================= How the crowd levels are defined ================= */}
      <CollapsibleSection
        title="How crowd levels are defined"
        subtitle="In plain language"
      >
        <ul className="space-y-2 text-sm text-slate-600">
          <li className="flex items-start gap-2">
            <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-crowd-low" aria-hidden="true" />
            <span>
              <strong className="text-slate-800">Low</strong> (0–40 %): plenty of
              room, you will usually find a seat.
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-crowd-moderate" aria-hidden="true" />
            <span>
              <strong className="text-slate-800">Moderate</strong> (40–65 %):
              comfortable, but a few people may wait for the next service.
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span
              className="mt-1 h-2.5 w-2.5 shrink-0 bg-crowd-high"
              style={{ clipPath: 'polygon(50% 0, 100% 100%, 0 100%)' }}
              aria-hidden="true"
            />
            <span>
              <strong className="text-slate-800">High</strong> (65–85 %): crowded,
              boarding is slow and queues form.
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span
              className="mt-1 h-2.5 w-2.5 shrink-0 bg-crowd-critical"
              style={{
                clipPath:
                  'polygon(30% 0, 70% 0, 100% 30%, 100% 70%, 70% 100%, 30% 100%, 0 70%, 0 30%)',
              }}
              aria-hidden="true"
            />
            <span>
              <strong className="text-slate-800">Critical</strong> (85 %+):
              overcrowded, some passengers may be left behind.
            </span>
          </li>
        </ul>
        <p className="mt-3 border-t border-slate-100 pt-2 text-[11px] leading-snug text-slate-500">
          How full the service is, as a share of the capacity offered by the
          planned service (vehicle capacity × vehicles per hour). The 85 %
          cut-off corresponds to roughly 0.85 m² of space per standing passenger
          in a crush-loaded vehicle. The expected wait is the headway of the
          service multiplied by 0.45 for a metro and 0.50 for a bus, plus 1.2
          minutes when the service is above 85 % full.
        </p>
      </CollapsibleSection>

      <DataNotice inline />
    </div>
  )
}
