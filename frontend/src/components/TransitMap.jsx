import { useMemo, useState } from 'react'

/**
 * The schematic NavaCity transit map.
 *
 * The network description carries a 0-100 coordinate for every station and
 * stop, so the map is drawn as plain SVG - no external tile server, no API
 * key and no network access required.
 *
 * Colour system (one scheme for the whole application):
 *   * metro lines are solid and use the indigo brand family,
 *   * bus routes are dashed and use the amber bus family,
 *   * the *selected* route is drawn thicker; every other route is dimmed.
 * The crowd palette is never used on the map, so a crowd colour can never be
 * mistaken for a route colour.
 */
const WIDTH = 1000
const HEIGHT = 1000
const PAD = 60

export const MAP_COLORS = {
  metro: '#1d3fbf',
  metroDim: '#a5b4fc',
  bus: '#b7791f',
  busDim: '#fcd34d',
  station: '#334155',
  stationFill: '#ffffff',
  interchange: '#1d3fbf',
}

function toPixels(place) {
  const x = PAD + (place.x / 100) * (WIDTH - 2 * PAD)
  const y = PAD + (place.y / 100) * (HEIGHT - 2 * PAD)
  return [x, y]
}

function routePoints(stops, placeById) {
  return stops
    .map((id) => placeById[id])
    .filter(Boolean)
    .map((place) => {
      const [x, y] = toPixels(place)
      return `${x},${y}`
    })
}

export default function TransitMap({
  network,
  selectedRouteId,
  onSelectRoute,
  height = 480,
  showLabels = true,
}) {
  const [hovered, setHovered] = useState(null)

  const geometry = useMemo(() => {
    if (!network) return { lines: [], places: [] }
    const placeById = Object.fromEntries(network.places.map((p) => [p.id, p]))

    const lines = []
    for (const line of network.metro_lines) {
      const points = routePoints(line.stops, placeById)
      if (points.length > 1) {
        lines.push({ id: line.id, name: line.name, mode: 'metro', points })
      }
    }
    for (const route of network.bus_routes) {
      const points = routePoints(route.stops, placeById)
      if (points.length > 1) {
        lines.push({ id: route.id, name: route.name, mode: 'bus', points })
      }
    }

    const places = network.places.map((place) => {
      const [x, y] = toPixels(place)
      return { ...place, px: x, py: y }
    })

    return { lines, places }
  }, [network])

  if (!network) {
    return <div className="skeleton w-full" style={{ height }} />
  }

  const hasSelection = Boolean(selectedRouteId)

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-full w-full"
        role="img"
        aria-label="Schematic map of the simulated NavaCity transit network"
      >
        <rect width={WIDTH} height={HEIGHT} fill="#f8fafc" rx={18} />

        {geometry.lines.map((line) => {
          const isSelected = line.id === selectedRouteId
          const dimmed = hasSelection && !isSelected
          const color = line.mode === 'metro' ? MAP_COLORS.metro : MAP_COLORS.bus
          const dimColor = line.mode === 'metro' ? MAP_COLORS.metroDim : MAP_COLORS.busDim
          return (
            <g key={`${line.mode}-${line.id}`}>
              <polyline
                points={line.points.join(' ')}
                fill="none"
                stroke={dimmed ? dimColor : color}
                strokeWidth={isSelected ? 9 : line.mode === 'metro' ? 5 : 3}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray={line.mode === 'bus' ? '10 7' : undefined}
                opacity={dimmed ? 0.45 : 1}
                className="cursor-pointer transition-opacity"
                onClick={() => onSelectRoute && onSelectRoute(line.id, line.mode)}
                onMouseEnter={() => setHovered(`${line.mode}-${line.id}`)}
                onMouseLeave={() => setHovered(null)}
              >
                <title>{`${line.id} ${line.name}`}</title>
              </polyline>
            </g>
          )
        })}

        {geometry.places.map((place) => {
          const isSelected =
            place.metro_lines.includes(selectedRouteId) ||
            place.bus_routes.includes(selectedRouteId)
          const isInterchange = place.metro_lines.length > 0 && place.bus_routes.length > 0
          const isHovered = hovered === place.id
          // The label is drawn for the selected route, the hovered place and
          // the interchanges, so the map stays readable at every zoom level.
          const showLabel = showLabels && (isSelected || isHovered || isInterchange)
          const onRight = place.px > WIDTH * 0.78
          const labelAnchor = onRight ? 'end' : 'start'
          const labelX = onRight ? place.px - 10 : place.px + 10
          return (
            <g
              key={place.id}
              onMouseEnter={() => setHovered(place.id)}
              onMouseLeave={() => setHovered(null)}
            >
              <circle
                cx={place.px}
                cy={place.py}
                r={isInterchange ? 7 : isSelected ? 6 : 4}
                fill={isSelected ? MAP_COLORS.interchange : MAP_COLORS.stationFill}
                stroke={isSelected ? MAP_COLORS.interchange : MAP_COLORS.station}
                strokeWidth={2}
                opacity={hasSelection && !isSelected ? 0.55 : 1}
              >
                <title>{place.name}</title>
              </circle>
              {showLabel && (
                <text
                  x={labelX}
                  y={place.py + 4}
                  textAnchor={labelAnchor}
                  className="pointer-events-none select-none"
                  fontSize="15"
                  fontWeight="600"
                  fill="#0f172a"
                  stroke="#f8fafc"
                  strokeWidth="3"
                  paintOrder="stroke"
                >
                  {place.name}
                </text>
              )}
            </g>
          )
        })}
      </svg>

      {/* ---------------- Legend ---------------- */}
      <div className="pointer-events-none absolute left-3 top-3 flex flex-col gap-1.5 rounded-control border border-slate-200 bg-white/95 p-2 text-[11px] shadow-sm">
        <span className="flex items-center gap-2 font-medium text-slate-700">
          <span
            aria-hidden="true"
            className="inline-block h-0.5 w-5 rounded-full"
            style={{ backgroundColor: MAP_COLORS.metro }}
          />
          Metro line (solid)
        </span>
        <span className="flex items-center gap-2 font-medium text-slate-700">
          <span
            aria-hidden="true"
            className="inline-block h-0.5 w-5 rounded-full"
            style={{
              backgroundImage: `repeating-linear-gradient(90deg, ${MAP_COLORS.bus} 0 5px, transparent 5px 9px)`,
            }}
          />
          Bus route (dashed)
        </span>
        <span className="flex items-center gap-2 font-medium text-slate-700">
          <span
            aria-hidden="true"
            className="inline-block h-2.5 w-2.5 rounded-full border-2 border-metro-700 bg-white"
          />
          Station or stop
        </span>
      </div>

      {selectedRouteId && (
        <div className="pointer-events-none absolute bottom-3 right-3 rounded-control border border-slate-200 bg-white/95 px-2 py-1 text-[11px] text-slate-600 shadow-sm">
          The selected route is drawn thicker.
        </div>
      )}
    </div>
  )
}
