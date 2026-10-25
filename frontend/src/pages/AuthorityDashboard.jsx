import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api, errorMessage, isUnauthorized } from '../api/client.js'
import { useAuth } from '../context/AuthContext.jsx'
import CrowdBadge from '../components/CrowdBadge.jsx'
import StatCard from '../components/StatCard.jsx'
import ChartCard, { LegendItem } from '../components/ChartCard.jsx'
import DataNotice from '../components/DataNotice.jsx'
import { EmptyState, ErrorState, LoadingSkeleton } from '../components/States.jsx'
import { formatDecimal, formatHour, formatNumber } from '../lib/format.js'

const SECTIONS = [
  { id: 'overview', label: 'Overview' },
  { id: 'metro', label: 'Metro' },
  { id: 'bus', label: 'Bus' },
  { id: 'model', label: 'Model & Data' },
]

const METRO_COLOR = '#1d3fbf'
const BUS_COLOR = '#b7791f'

/** The colour family of a transport mode. */
function modeColor(mode) {
  return mode === 'bus' ? BUS_COLOR : METRO_COLOR
}

function crowdLevelFor(occupancyPct) {
  if (occupancyPct >= 85) return 'Critical'
  if (occupancyPct >= 65) return 'High'
  if (occupancyPct >= 40) return 'Moderate'
  return 'Low'
}

export default function AuthorityDashboard() {
  const [section, setSection] = useState('overview')
  const [stats, setStats] = useState(null)
  const [alerts, setAlerts] = useState(null)
  const [crowd, setCrowd] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [modeSummary, setModeSummary] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [routeFilter, setRouteFilter] = useState('all')
  const [severityFilter, setSeverityFilter] = useState('all')
  const [dateFilter, setDateFilter] = useState('')
  const { handleUnauthorized, session, signOut, busy } = useAuth()

  // The mode of the current section: the Metro and the Bus tabs are the same
  // page, filtered to one transport mode.
  const sectionMode = section === 'bus' ? 'bus' : section === 'metro' ? 'metro' : null

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [statsData, alertsData, crowdData, summaryData] = await Promise.all([
        api.authorityStats(sectionMode ? { mode: sectionMode } : {}),
        api.alerts({ limit: 60, mode: sectionMode || undefined }),
        api.crowdSummary(sectionMode ? { mode: sectionMode } : {}),
        api.modeSummary(),
      ])
      setStats(statsData)
      setAlerts(alertsData)
      setCrowd(crowdData)
      setModeSummary(summaryData)

      // The metrics file is optional - the dashboard works without it.
      api
        .modelMetrics()
        .then(setMetrics)
        .catch(() => setMetrics(null))
    } catch (err) {
      // The backend rejected the session: send the operator back to the
      // sign-in screen instead of showing a broken dashboard.
      if (isUnauthorized(err)) {
        handleUnauthorized()
        return
      }
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [handleUnauthorized, sectionMode])

  useEffect(() => {
    load()
  }, [load])

  const filteredAlerts = useMemo(() => {
    if (!alerts) return []
    let list = alerts.alerts
    if (sectionMode) {
      list = list.filter((alert) => alert.mode === sectionMode)
    }
    if (routeFilter !== 'all') {
      list = list.filter((alert) => alert.route_id === routeFilter)
    }
    if (severityFilter !== 'all') {
      list = list.filter((alert) => alert.severity === severityFilter)
    }
    return list
  }, [alerts, sectionMode, routeFilter, severityFilter])

  // The routes of the network, used by the route filter.
  const routeOptions = useMemo(
    () => (stats?.route_analytics || []).map((item) => item.route_id),
    [stats],
  )

  // The route table, sorted by the selected column.
  const [sortKey, setSortKey] = useState('mean_occupancy_pct')
  const [sortDir, setSortDir] = useState('desc')

  const routeRows = useMemo(() => {
    const rows = [...(stats?.route_analytics || [])]
    rows.sort((a, b) => {
      const av = Number(a[sortKey] ?? 0)
      const bv = Number(b[sortKey] ?? 0)
      return sortDir === 'desc' ? bv - av : av - bv
    })
    return rows
  }, [stats, sortKey, sortDir])

  const toggleSort = (key) => {
    if (sortKey === key) {
      setSortDir((dir) => (dir === 'desc' ? 'asc' : 'desc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const sortIndicator = (key) =>
    sortKey === key ? (sortDir === 'desc' ? ' ↓' : ' ↑') : ''

  // The busiest routes, for the "top routes" chart.
  const topRoutes = useMemo(
    () => (stats?.route_analytics || []).slice().sort(
      (a, b) => b.mean_occupancy_pct - a.mean_occupancy_pct,
    ).slice(0, 12),
    [stats],
  )

  const hourlyChart = useMemo(
    () =>
      (stats?.hourly_analytics || []).map((item) => ({
        hour: item.hour,
        label: formatHour(item.hour),
        metro: item.metro_passengers,
        bus: item.bus_passengers,
        total: item.mean_passengers,
        crowd: item.crowd_level,
      })),
    [stats],
  )

  // The weekday / weekend profile of the current mode.
  const profileChart = useMemo(
    () =>
      (stats?.weekday_weekend_profile || []).map((item) => ({
        hour: item.hour,
        label: formatHour(item.hour),
        weekday: item.weekday_occupancy_pct,
        weekend: item.weekend_occupancy_pct,
      })),
    [stats],
  )

  // The peak hours of the current mode, sorted by the mean occupancy.
  const peakHours = useMemo(
    () =>
      [...(stats?.hourly_analytics || [])]
        .sort((a, b) => b.mean_occupancy_pct - a.mean_occupancy_pct)
        .slice(0, 6),
    [stats],
  )

  const routeChart = useMemo(
    () =>
      (stats?.route_analytics || []).slice(0, 12).map((item) => ({
        route_id: item.route_id,
        name: item.route_name,
        mode: item.mode,
        total: item.total_passengers,
        mean_occupancy_pct: item.mean_occupancy_pct,
        overcrowded_share_pct: item.overcrowded_share_pct,
      })),
    [stats],
  )

  // The busiest routes of the network, sorted by the total simulated demand.
  const topRoutesChart = useMemo(
    () =>
      topRoutes.map((item) => ({
        route_id: item.route_id,
        name: item.route_name,
        mode: item.mode,
        total: item.total_passengers,
        mean_occupancy_pct: item.mean_occupancy_pct,
        overcrowded_share_pct: item.overcrowded_share_pct,
      })),
    [topRoutes],
  )

  if (error) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-slate-900">
          Transport authority dashboard
        </h1>
        <ErrorState
          title="The NavaCity API is not reachable"
          message={error}
          onRetry={load}
        />
      </div>
    )
  }

  if (loading || !stats) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-slate-900">
          Transport authority dashboard
        </h1>
        <div className="card">
          <LoadingSkeleton label="Loading the authority statistics…" rows={5} />
        </div>
      </div>
    )
  }

  const sectionTitle =
    section === 'overview'
      ? 'Overview'
      : section === 'metro'
        ? 'Metro'
        : section === 'bus'
          ? 'Bus'
          : 'Model & Data'
  const sectionDescription =
    section === 'overview'
      ? 'Demand, occupancy and overcrowding across the whole simulated network.'
      : section === 'metro'
        ? 'Metro lines only: occupancy profile, route table, alerts and frequency recommendations.'
        : section === 'bus'
          ? 'Bus routes only: occupancy profile, route table, alerts and frequency recommendations.'
          : 'The measured model performance and the shape of the simulated dataset.'

  return (
    <div className="animate-fade-in">
      {/* ================= Header ================= */}
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">
            Transport authority dashboard
          </h1>
          <p className="text-sm text-slate-500">
            Signed in as transport authority
            {session
              ? ` · session until ${new Date(session.expires_at * 1000).toLocaleTimeString()}`
              : ''}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" className="btn-ghost btn-sm" onClick={load}>
            Refresh
          </button>
          <button
            type="button"
            className="btn-ghost btn-sm"
            onClick={signOut}
            disabled={busy}
          >
            Sign out
          </button>
        </div>
      </div>

      <DataNotice inline />

      {/* ================= Sidebar + content ================= */}
      <div className="mt-4 flex gap-6">
        <nav
          className="hidden w-52 shrink-0 lg:block"
          aria-label="Sections of the authority dashboard"
        >
          <ul className="sticky top-24 space-y-1">
            {SECTIONS.map((item) => {
              const active = section === item.id
              return (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => setSection(item.id)}
                    aria-current={active ? 'page' : undefined}
                    className={`flex w-full min-h-[44px] items-center rounded-control px-3 py-2 text-left text-sm font-medium transition ${
                      active
                        ? 'bg-metro-700 text-white'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    {item.label}
                  </button>
                </li>
              )
            })}
          </ul>
        </nav>

        <div className="min-w-0 flex-1 space-y-4">
          {/* The mobile version of the navigation. */}
          <div className="lg:hidden">
            <label className="label" htmlFor="section-select">
              Section
            </label>
            <select
              id="section-select"
              className="select"
              value={section}
              onChange={(event) => setSection(event.target.value)}
            >
              {SECTIONS.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">{sectionTitle}</h2>
              <p className="text-sm text-slate-500">{sectionDescription}</p>
            </div>
            <div className="flex flex-wrap items-end gap-2">
              <div>
                <label className="label" htmlFor="date-filter">
                  Date
                </label>
                <input
                  id="date-filter"
                  type="date"
                  className="select w-auto"
                  value={dateFilter}
                  onChange={(event) => setDateFilter(event.target.value)}
                />
              </div>
              <div>
                <label className="label" htmlFor="route-filter">
                  Route
                </label>
                <select
                  id="route-filter"
                  className="select w-auto"
                  value={routeFilter}
                  onChange={(event) => setRouteFilter(event.target.value)}
                >
                  <option value="all">All routes</option>
                  {routeOptions.map((routeId) => (
                    <option key={routeId} value={routeId}>
                      {routeId}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label" htmlFor="severity-filter">
                  Severity
                </label>
                <select
                  id="severity-filter"
                  className="select w-auto"
                  value={severityFilter}
                  onChange={(event) => setSeverityFilter(event.target.value)}
                >
                  <option value="all">All</option>
                  <option value="warning">High (warning)</option>
                  <option value="critical">Critical</option>
                </select>
              </div>
            </div>
          </div>

          {/* ================= OVERVIEW ================= */}
          {section === 'overview' && (
            <>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {stats.kpis.map((kpi) => (
                  <StatCard
                    key={kpi.key}
                    label={kpi.label}
                    value={kpi.unit === '%' ? formatDecimal(kpi.value, 1) : formatNumber(kpi.value)}
                    unit={kpi.unit === '%' ? '%' : undefined}
                    detail={kpi.detail}
                  />
                ))}
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                {(modeSummary?.comparison || stats.mode_comparison).map((item) => (
                  <section
                    key={item.mode}
                    className="card"
                    aria-label={`${item.mode} summary`}
                  >
                    <div className="flex items-center justify-between">
                      <h3
                        className={`text-base font-semibold ${
                          item.mode === 'bus' ? 'text-bus-700' : 'text-metro-700'
                        }`}
                      >
                        {item.mode === 'bus' ? 'Bus' : 'Metro'}
                      </h3>
                      <span className="text-xs text-slate-500">
                        {item.routes} routes · {formatNumber(item.records)} observations
                      </span>
                    </div>
                    <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                      <div>
                        <dt className="text-xs text-slate-500">Mean occupancy</dt>
                        <dd className="text-lg font-semibold tabular-nums text-slate-900">
                          {formatDecimal(item.mean_occupancy_pct, 1)} %
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-slate-500">Overcrowded share</dt>
                        <dd className="text-lg font-semibold tabular-nums text-slate-900">
                          {formatDecimal(item.overcrowded_share_pct, 1)} %
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-slate-500">Peak load, pax/vehicle</dt>
                        <dd className="text-lg font-semibold tabular-nums text-slate-900">
                          {formatDecimal(item.passengers_per_vehicle, 1)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-slate-500">Busiest route</dt>
                        <dd className="text-lg font-semibold tabular-nums text-slate-900">
                          {modeSummary?.busiest_route?.[item.mode] || '—'}
                        </dd>
                      </div>
                    </dl>
                    <p className="mt-3 border-t border-slate-100 pt-2 text-[11px] leading-snug text-slate-500">
                      Occupancy and passengers per vehicle are the comparable
                      figures: a metro vehicle seats 320, a bus 48, so the raw
                      passenger totals are shown as secondary information only
                      ({formatNumber(item.total_passengers)} passengers in
                      total, {formatDecimal(item.share_of_records_pct, 1)} % of
                      the observations).
                    </p>
                  </section>
                ))}
              </div>

              <ChartCard
                title="Demand by hour of day — metro vs bus"
                subtitle="Mean passengers per route-stretch-hour"
                legend={
                  <>
                    <LegendItem color={METRO_COLOR} label="Metro" />
                    <LegendItem color={BUS_COLOR} label="Bus" />
                    <LegendItem color="#0f172a" label="All modes" dashed />
                  </>
                }
                caption={`Mean simulated passengers per route-stretch-hour for
                  every hour of the day. Peak hours: ${stats.peak_hours
                    .map((h) => formatHour(h))
                    .join(', ')}. Data period: ${stats.data_period?.start} to
                  ${stats.data_period?.end} (simulated), 4 sampled hours per
                  route-stretch per day.`}
              >
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={hourlyChart} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
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
                      width={62}
                      label={{
                        value: 'Passengers per route-stretch-hour',
                        angle: -90,
                        position: 'insideLeft',
                        fontSize: 11,
                        fill: '#64748b',
                      }}
                    />
                    <Tooltip
                      formatter={(value, name) => [
                        `${formatNumber(value)} passengers`,
                        name === 'metro' ? 'Metro' : name === 'bus' ? 'Bus' : 'All modes',
                      ]}
                      contentStyle={{ fontSize: 12, borderRadius: 8 }}
                    />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Line
                      type="monotone"
                      dataKey="metro"
                      stroke={METRO_COLOR}
                      strokeWidth={2.5}
                      dot={false}
                      name="metro"
                    />
                    <Line
                      type="monotone"
                      dataKey="bus"
                      stroke={BUS_COLOR}
                      strokeWidth={2.5}
                      dot={false}
                      name="bus"
                    />
                    <Line
                      type="monotone"
                      dataKey="total"
                      stroke="#0f172a"
                      strokeWidth={1.5}
                      strokeDasharray="4 4"
                      dot={false}
                      name="total"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </ChartCard>

              <div className="grid gap-4 lg:grid-cols-2">
                <section className="card" aria-label="Crowd level distribution">
                  <h3 className="card-title">Distribution of the crowd levels</h3>
                  <p className="mt-1 text-xs text-slate-500">
                    Share of the simulated observations in each crowd level.
                  </p>
                  {crowd && (
                    <ul className="mt-3 space-y-2">
                      {crowd.levels.map((level) => (
                        <li key={level.crowd_level} className="flex items-center gap-3">
                          <CrowdBadge level={level.crowd_level} size="sm" />
                          <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-200">
                            <div
                              className="h-full rounded-full bg-slate-500"
                              style={{ width: `${level.share_pct}%` }}
                            />
                          </div>
                          <span className="w-16 text-right text-xs tabular-nums text-slate-600">
                            {formatDecimal(level.share_pct, 1)} %
                          </span>
                          <span className="w-24 text-right text-xs tabular-nums text-slate-500">
                            {formatNumber(level.count)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                  <p className="mt-3 border-t border-slate-100 pt-2 text-[11px] leading-snug text-slate-500">
                    Mean occupancy {formatDecimal(crowd?.average_occupancy_pct, 1)} %.
                    {formatNumber(crowd?.overcrowded_records)} observations (
                    {formatDecimal(crowd?.overcrowded_share_pct, 1)} %) are at or
                    above 80 % occupancy.
                  </p>
                </section>

                <section className="card" aria-label="Data period">
                  <h3 className="card-title">The simulated dataset</h3>
                  <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                    <div>
                      <dt className="text-xs text-slate-500">Data period</dt>
                      <dd className="font-semibold tabular-nums text-slate-800">
                        {stats.data_period?.start} → {stats.data_period?.end}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-slate-500">Observations</dt>
                      <dd className="font-semibold tabular-nums text-slate-800">
                        {formatNumber(stats.data_period?.records ?? stats.total_records)}
                      </dd>
                    </div>
                    <div className="col-span-2">
                      <dt className="text-xs text-slate-500">Granularity</dt>
                      <dd className="text-slate-700">
                        {stats.data_period?.granularity ||
                          '4 sampled hours per route-stretch per day'}
                      </dd>
                    </div>
                    <div className="col-span-2">
                      <dt className="text-xs text-slate-500">Routes</dt>
                      <dd className="text-slate-700">
                        {stats.total_routes} routes · {stats.total_stations} metro
                        stations · {stats.total_stops} bus stops
                      </dd>
                    </div>
                  </dl>
                </section>
              </div>
            </>
          )}

          {/* ================= METRO and BUS (the same layout) ========== */}
          {(section === 'metro' || section === 'bus') && (
            <>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {stats.kpis.map((kpi) => (
                  <StatCard
                    key={kpi.key}
                    label={kpi.label}
                    value={kpi.unit === '%' ? formatDecimal(kpi.value, 1) : formatNumber(kpi.value)}
                    unit={kpi.unit === '%' ? '%' : undefined}
                    detail={kpi.detail}
                  />
                ))}
              </div>

              <ChartCard
                title={`Hourly occupancy profile — ${section === 'bus' ? 'bus' : 'metro'}`}
                subtitle="Weekday against weekend"
                legend={
                  <>
                    <LegendItem color={modeColor(sectionMode)} label="Weekday" />
                    <LegendItem color="#94a3b8" label="Weekend" dashed />
                  </>
                }
                caption={`Mean occupancy of the sampled route-stretch-hours, in
                  percent of the hourly capacity, for a weekday and for a
                  weekend. Data period: ${stats.data_period?.start} to
                  ${stats.data_period?.end} (simulated), 4 sampled hours per
                  route-stretch per day.`}
              >
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={profileChart} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
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
                      unit="%"
                      label={{
                        value: 'Mean occupancy',
                        angle: -90,
                        position: 'insideLeft',
                        fontSize: 11,
                        fill: '#64748b',
                      }}
                    />
                    <Tooltip
                      formatter={(value, name) => [
                        `${formatDecimal(value, 1)} %`,
                        name === 'weekday' ? 'Weekday' : 'Weekend',
                      ]}
                      contentStyle={{ fontSize: 12, borderRadius: 8 }}
                    />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Line
                      type="monotone"
                      dataKey="weekday"
                      stroke={modeColor(sectionMode)}
                      strokeWidth={2.5}
                      dot={false}
                      name="weekday"
                    />
                    <Line
                      type="monotone"
                      dataKey="weekend"
                      stroke="#94a3b8"
                      strokeWidth={2}
                      strokeDasharray="5 4"
                      dot={false}
                      name="weekend"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </ChartCard>

              <div className="grid gap-4 lg:grid-cols-2">
                <section className="card" aria-label="Peak hours">
                  <h3 className="card-title">Peak hours</h3>
                  <p className="mt-1 text-xs text-slate-500">
                    The six hours with the highest mean occupancy.
                  </p>
                  <div className="table-wrap mt-3">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th scope="col">Hour</th>
                          <th scope="col" className="num">Mean occupancy</th>
                          <th scope="col" className="num">Overcrowded share</th>
                        </tr>
                      </thead>
                      <tbody>
                        {peakHours.map((item) => (
                          <tr key={item.hour}>
                            <td className="tabular-nums">{formatHour(item.hour)}</td>
                            <td className="num tabular-nums">
                              {formatDecimal(item.mean_occupancy_pct, 1)} %
                            </td>
                            <td className="num tabular-nums">
                              {formatDecimal(item.overcrowded_share_pct, 1)} %
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="mt-3 border-t border-slate-100 pt-2 text-[11px] leading-snug text-slate-500">
                    The overcrowded share is the share of the observations of that
                    hour that are at or above 80 % occupancy.
                  </p>
                </section>

                <ChartCard
                  title="Busiest routes"
                  subtitle="Mean occupancy per route"
                  legend={<LegendItem color={modeColor(sectionMode)} label="Mean occupancy" />}
                  caption={`Mean occupancy of the 12 busiest routes of the
                    ${section === 'bus' ? 'bus' : 'metro'} network, in percent of
                    the hourly capacity. Data period: ${stats.data_period?.start}
                    to ${stats.data_period?.end} (simulated).`}
                >
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart
                      data={topRoutes}
                      layout="vertical"
                      margin={{ top: 0, right: 16, left: 8, bottom: 0 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                      <XAxis
                        type="number"
                        tick={{ fontSize: 11, fill: '#64748b' }}
                        unit="%"
                        label={{
                          value: 'Mean occupancy',
                          position: 'insideBottom',
                          offset: -2,
                          fontSize: 11,
                          fill: '#64748b',
                        }}
                      />
                      <YAxis
                        type="category"
                        dataKey="route_id"
                        tick={{ fontSize: 11, fill: '#334155' }}
                        width={44}
                      />
                      <Tooltip
                        formatter={(value) => [`${formatDecimal(value, 1)} %`, 'Mean occupancy']}
                        contentStyle={{ fontSize: 12, borderRadius: 8 }}
                      />
                      <Bar
                        dataKey="mean_occupancy_pct"
                        radius={[0, 4, 4, 0]}
                        fill={modeColor(sectionMode)}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartCard>
              </div>

              <section className="card" aria-label="Route table">
                <h3 className="card-title">Routes</h3>
                <p className="mt-1 text-xs text-slate-500">
                  Click a column heading to sort the table.
                </p>
                <div className="table-wrap mt-3">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th scope="col">Route</th>
                        <th scope="col">Name</th>
                        <th scope="col" className="num">
                          <button
                            type="button"
                            onClick={() => toggleSort('mean_occupancy_pct')}
                            className="font-semibold uppercase tracking-wide"
                          >
                            Mean occupancy{sortIndicator('mean_occupancy_pct')}
                          </button>
                        </th>
                        <th scope="col" className="num">
                          <button
                            type="button"
                            onClick={() => toggleSort('overcrowded_share_pct')}
                            className="font-semibold uppercase tracking-wide"
                          >
                            Overcrowded share{sortIndicator('overcrowded_share_pct')}
                          </button>
                        </th>
                        <th scope="col" className="num">
                          <button
                            type="button"
                            onClick={() => toggleSort('peak_load_per_vehicle')}
                            className="font-semibold uppercase tracking-wide"
                          >
                            Peak load, pax/vehicle{sortIndicator('peak_load_per_vehicle')}
                          </button>
                        </th>
                        <th scope="col" className="num">Peak hour</th>
                        <th scope="col">Busiest stretch</th>
                      </tr>
                    </thead>
                    <tbody>
                      {routeRows.map((item) => (
                        <tr key={item.route_id}>
                          <td className="font-semibold tabular-nums text-slate-900">
                            {item.route_id}
                          </td>
                          <td>{item.route_name}</td>
                          <td className="num tabular-nums">
                            {formatDecimal(item.mean_occupancy_pct, 1)} %
                          </td>
                          <td className="num tabular-nums">
                            {formatDecimal(item.overcrowded_share_pct, 1)} %
                          </td>
                          <td className="num tabular-nums">
                            {formatDecimal(item.peak_load_per_vehicle, 1)}
                          </td>
                          <td className="num tabular-nums">{formatHour(item.peak_hour)}</td>
                          <td className="text-xs text-slate-600">
                            {item.busiest_segment_names || item.busiest_segment}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="mt-3 border-t border-slate-100 pt-2 text-[11px] leading-snug text-slate-500">
                  Peak load is the mean number of passengers per vehicle per hour
                  in the busiest hour of the route, which is the figure that can
                  be compared between a {section === 'bus' ? '48-seat bus' : '320-seat metro vehicle'}.
                </p>
              </section>

              <section className="card" aria-label="Overcrowding alerts">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="card-title">Overcrowding alerts</h3>
                  <span className="text-xs text-slate-500">
                    Showing {filteredAlerts.length} of {alerts?.count ?? 0}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  Route stretches and hours whose simulated occupancy is at or
                  above {alerts?.threshold_pct ?? 80} % of the offered capacity.
                </p>
                {filteredAlerts.length === 0 ? (
                  <div className="mt-3">
                    <EmptyState
                      title="No matching alerts"
                      message="No alert matches the current filters."
                    />
                  </div>
                ) : (
                  <div className="table-wrap mt-3">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th scope="col">Route</th>
                          <th scope="col">Stretch</th>
                          <th scope="col">Date</th>
                          <th scope="col" className="num">Hour</th>
                          <th scope="col" className="num">Occupancy</th>
                          <th scope="col">Severity</th>
                          <th scope="col">Recommended action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredAlerts.map((alert) => (
                          <tr
                            key={`${alert.route_id}-${alert.segment_id}-${alert.date}-${alert.hour}`}
                          >
                            <td className="font-semibold tabular-nums text-slate-900">
                              {alert.route_id}
                            </td>
                            <td className="text-xs text-slate-600">
                              {alert.origin_name} → {alert.dest_name}
                            </td>
                            <td className="tabular-nums text-xs">{alert.date}</td>
                            <td className="num tabular-nums">{formatHour(alert.hour)}</td>
                            <td className="num tabular-nums">
                              {formatDecimal(alert.mean_occupancy_pct, 1)} %
                            </td>
                            <td>
                              <CrowdBadge
                                level={alert.crowd_level}
                                occupancyPct={alert.mean_occupancy_pct}
                                size="sm"
                              />
                            </td>
                            <td className="text-xs text-slate-600">
                              {alert.severity === 'critical'
                                ? 'Add 1 vehicle per hour in this hour.'
                                : 'Review the timetable for this hour.'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              <section className="card" aria-label="Service frequency recommendations">
                <h3 className="card-title">Service-frequency recommendations</h3>
                <p className="mt-1 text-xs text-slate-500">
                  A planning heuristic, not an optimised schedule. A human
                  planner has to validate every change.
                </p>
                {stats.recommendations.length === 0 ? (
                  <div className="mt-3">
                    <EmptyState
                      title="No recommendation"
                      message="No route-hour of this mode needs a frequency change."
                    />
                  </div>
                ) : (
                  <ul className="mt-3 grid gap-3 md:grid-cols-2">
                    {stats.recommendations.map((rec) => (
                      <li
                        key={`${rec.route_id}-${rec.hour}`}
                        className="rounded-control border border-slate-200 p-3"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p className="text-sm font-semibold text-slate-900">
                              {rec.route_id} · {rec.route_name}
                            </p>
                            <p className="text-xs text-slate-500">
                              {formatHour(rec.hour)} · {rec.segment_names || rec.segment_id}
                            </p>
                          </div>
                          <span className="badge bg-slate-100 text-slate-700">
                            {rec.confidence} confidence
                          </span>
                        </div>
                        <p className="mt-2 text-sm text-slate-700">
                          <span className="font-semibold tabular-nums">
                            {rec.current_frequency} → {rec.recommended_frequency}
                          </span>{' '}
                          vehicles per hour
                        </p>
                        <p className="mt-1 text-[11px] leading-snug text-slate-500">
                          <strong className="text-slate-600">Rule:</strong> {rec.rule}
                        </p>
                        <p className="mt-1 text-[11px] leading-snug text-slate-500">
                          {rec.reason}
                        </p>
                        <p className="mt-1 text-[11px] leading-snug text-slate-400">
                          {rec.disclaimer}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </>
          )}

          {/* ================= MODEL & DATA ================= */}
          {section === 'model' && (
            <>
              {!metrics ? (
                <EmptyState
                  title="No metrics file"
                  message="Run 'python ml\\train_model.py' to produce the model evaluation."
                />
              ) : (
                <>
                  <div className="card">
                    <h3 className="card-title">What these numbers mean</h3>
                    <p className="mt-2 text-sm text-slate-600">
                      These metrics are measured on <strong>simulated</strong>{' '}
                      data. They describe how well the model fits the rule-based
                      simulator it was trained on. They say <em>nothing</em>{' '}
                      about how such a system would perform on real passenger
                      counts.
                    </p>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    {Object.entries(metrics.modes || {}).map(([mode, info]) => (
                      <section key={mode} className="card" aria-label={`${mode} metrics`}>
                        <div className="flex items-center justify-between">
                          <h3
                            className={`text-base font-semibold ${
                              mode === 'bus' ? 'text-bus-700' : 'text-metro-700'
                            }`}
                          >
                            {mode === 'bus' ? 'Bus' : 'Metro'}
                          </h3>
                          <span className="badge bg-slate-100 text-slate-700">
                            {info.best_model}
                          </span>
                        </div>
                        <dl className="mt-3 grid grid-cols-3 gap-2 text-sm">
                          <div>
                            <dt className="text-xs text-slate-500">MAE</dt>
                            <dd className="font-semibold tabular-nums text-slate-900">
                              {formatDecimal(info.time_ordered_metrics?.mae, 2)}
                            </dd>
                          </div>
                          <div>
                            <dt className="text-xs text-slate-500">RMSE</dt>
                            <dd className="font-semibold tabular-nums text-slate-900">
                              {formatDecimal(info.time_ordered_metrics?.rmse, 2)}
                            </dd>
                          </div>
                          <div>
                            <dt className="text-xs text-slate-500">R²</dt>
                            <dd className="font-semibold tabular-nums text-slate-900">
                              {formatDecimal(info.time_ordered_metrics?.r2, 4)}
                            </dd>
                          </div>
                        </dl>
                        <p className="mt-3 text-[11px] leading-snug text-slate-500">
                          Test period starts {info.test_start_date} ·{' '}
                          {formatNumber(info.test_rows)} test rows of{' '}
                          {formatNumber(info.train_rows)} training rows. The
                          split is time ordered, so the model is always tested
                          on the days that come last.
                        </p>
                      </section>
                    ))}
                  </div>

                  <section className="card" aria-label="The simulated dataset">
                    <h3 className="card-title">The simulated dataset</h3>
                    <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                      <div>
                        <dt className="text-xs text-slate-500">Data period</dt>
                        <dd className="font-semibold tabular-nums text-slate-800">
                          {metrics.dataset?.date_min} → {metrics.dataset?.date_max}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-slate-500">Records</dt>
                        <dd className="font-semibold tabular-nums text-slate-800">
                          {formatNumber(metrics.dataset?.rows)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-slate-500">Routes</dt>
                        <dd className="font-semibold tabular-nums text-slate-800">
                          {metrics.dataset?.routes}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-slate-500">Split</dt>
                        <dd className="text-slate-700">{metrics.split?.strategy}</dd>
                      </div>
                      <div className="col-span-2">
                        <dt className="text-xs text-slate-500">Granularity</dt>
                        <dd className="text-slate-700">
                          4 sampled hours per route-stretch per day (the two
                          commuter peaks plus two other hours). The 24 hours of
                          the day are therefore <em>not</em> a complete hourly
                          series of any single day.
                        </dd>
                      </div>
                    </dl>
                  </section>

                  <section className="card" aria-label="Feature importance">
                    <h3 className="card-title">Feature importance</h3>
                    <p className="mt-1 text-xs text-slate-500">
                      The mean importance of the ten strongest features across
                      both modes.
                    </p>
                    <ul className="mt-3 space-y-2">
                      {Object.entries(metrics.mean_feature_importance || {})
                        .slice(0, 10)
                        .map(([name, value]) => (
                          <li key={name} className="flex items-center gap-3">
                            <span className="w-44 shrink-0 text-xs text-slate-600">
                              {name}
                            </span>
                            <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-200">
                              <div
                                className="h-full rounded-full bg-metro-700"
                                style={{ width: `${Math.min(100, (Number(value) / 0.35) * 100)}%` }}
                              />
                            </div>
                            <span className="w-16 text-right text-xs tabular-nums text-slate-500">
                              {formatDecimal(value, 4)}
                            </span>
                          </li>
                        ))}
                    </ul>
                  </section>

                  <section className="card" aria-label="Evaluation plots">
                    <h3 className="card-title">Evaluation plots</h3>
                    <p className="mt-1 text-xs text-slate-500">
                      Written by <code>ml/train_model.py</code> into{' '}
                      <code>ml/artifacts</code>.
                    </p>
                    <ul className="mt-3 grid gap-2 text-sm text-slate-600 sm:grid-cols-2">
                      <li>actual_vs_predicted_metro.png — predicted against the actual simulated demand, metro</li>
                      <li>actual_vs_predicted_bus.png — predicted against the actual simulated demand, bus</li>
                      <li>residuals_metro.png — the residuals of the metro model</li>
                      <li>residuals_bus.png — the residuals of the bus model</li>
                      <li>feature_importance.png — the importance of every model input</li>
                      <li>forecast_vs_history.png — a forecast against the simulated history</li>
                    </ul>
                  </section>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
