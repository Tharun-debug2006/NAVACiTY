"""Aggregation helpers that back the authority dashboard.

All numbers are computed from the SIMULATED records stored in SQLite.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import Integer, func, select
from sqlalchemy.orm import Session

from navacity_core.config import (
    CROWD_HIGH_MAX,
    CROWD_LOW_MAX,
    CROWD_MODERATE_MAX,
    OVERCROWDING_ALERT_THRESHOLD,
    crowd_level_for,
)

from ..database import DemandRecord, Place, Route
from ..schemas import (
    AlternativesResponse,
    AlternativeRoute,
    AuthorityStatsResponse,
    CrowdSummaryEntry,
    CrowdSummaryResponse,
    HourlyAnalytics,
    HourlyPoint,
    KpiCard,
    ModeComparison,
    OvercrowdingAlert,
    RouteAnalytics,
    ServiceRecommendation,
)

DATA_NOTICE = (
    "SIMULATED DATA - NavaCity is a fictional city. All figures are produced "
    "by a rule-based simulator and a model trained on that simulated data."
)

RECOMMENDATION_DISCLAIMER = (
    "Recommendation only - based on simulated demand. Not a guaranteed "
    "optimal service plan; a human planner must validate it."
)


# --------------------------------------------------------------------------
# Basic counters
# --------------------------------------------------------------------------
def count_records(session: Session) -> int:
    return int(session.scalar(select(func.count()).select_from(DemandRecord)) or 0)


def count_routes(session: Session, mode: str | None = None) -> int:
    stmt = select(func.count()).select_from(Route)
    if mode:
        stmt = stmt.where(Route.mode == mode)
    return int(session.scalar(stmt) or 0)


def _count_true(column) -> object:
    """A SQL expression that counts the rows where a boolean column is true.

    ``func.sum()`` on a Boolean column does **not** return a count on SQLite:
    it returns the boolean ``True``.  The column is therefore cast to an
    integer first, so that the result is the number of matching rows.
    """
    return func.sum(func.cast(column, Integer))


def count_places(session: Session, kind: str | None = None) -> int:
    stmt = select(func.count()).select_from(Place)
    if kind:
        stmt = stmt.where(Place.kind == kind)
    return int(session.scalar(stmt) or 0)


def count_bus_served_places(session: Session) -> int:
    """The number of places a bus can stop at.

    ``Place.kind == "stop"`` only counts the five stops that are *not* metro
    stations.  A bus also stops at 37 metro stations, so the useful number for
    a planner is every place served by at least one bus route.
    """
    stmt = select(func.count()).select_from(Place).where(Place.bus_routes != "")
    return int(session.scalar(stmt) or 0)


def count_metro_served_places(session: Session) -> int:
    """The number of places served by at least one metro line."""
    stmt = select(func.count()).select_from(Place).where(Place.metro_lines != "")
    return int(session.scalar(stmt) or 0)


def dataset_date_range(session: Session) -> tuple[str | None, str | None]:
    min_date = session.scalar(select(func.min(DemandRecord.date)))
    max_date = session.scalar(select(func.max(DemandRecord.date)))
    return (min_date, max_date)


# --------------------------------------------------------------------------
# Crowd summary
# --------------------------------------------------------------------------
def crowd_summary(
    session: Session, mode: str | None = None, route_id: str | None = None
) -> CrowdSummaryResponse:
    """Distribution of the crowd levels over the selected records."""
    stmt = select(
        DemandRecord.crowd_level,
        func.count(DemandRecord.id),
        func.avg(DemandRecord.occupancy_pct),
    ).group_by(DemandRecord.crowd_level)
    if mode:
        stmt = stmt.where(DemandRecord.mode == mode)
    if route_id:
        stmt = stmt.where(DemandRecord.route_id == route_id)

    rows = {level: (0, 0.0) for level in ("Low", "Moderate", "High", "Critical")}
    total = 0
    for level, count, mean_occ in session.execute(stmt):
        rows[level] = (int(count), float(mean_occ or 0.0))
        total += int(count)

    levels = []
    for level in ("Low", "Moderate", "High", "Critical"):
        count, mean_occ = rows[level]
        levels.append(
            CrowdSummaryEntry(
                crowd_level=level,
                count=count,
                share_pct=round(100.0 * count / total, 2) if total else 0.0,
                mean_occupancy_pct=round(mean_occ, 2),
            )
        )

    avg_stmt = select(func.avg(DemandRecord.occupancy_pct))
    over_stmt = select(func.count(DemandRecord.id)).where(
        DemandRecord.occupancy_pct >= OVERCROWDING_ALERT_THRESHOLD * 100.0
    )
    if mode:
        avg_stmt = avg_stmt.where(DemandRecord.mode == mode)
        over_stmt = over_stmt.where(DemandRecord.mode == mode)
    if route_id:
        avg_stmt = avg_stmt.where(DemandRecord.route_id == route_id)
        over_stmt = over_stmt.where(DemandRecord.route_id == route_id)

    avg_occ = float(session.scalar(avg_stmt) or 0.0)
    overcrowded = int(session.scalar(over_stmt) or 0)

    return CrowdSummaryResponse(
        mode=mode,
        route_id=route_id,
        total_records=total,
        data_notice=DATA_NOTICE,
        levels=levels,
        average_occupancy_pct=round(avg_occ, 2),
        overcrowded_records=overcrowded,
        overcrowded_share_pct=round(100.0 * overcrowded / total, 2) if total else 0.0,
    )


# --------------------------------------------------------------------------
# Overcrowding alerts
# --------------------------------------------------------------------------
def overcrowding_alerts(
    session: Session,
    mode: str | None = None,
    date_filter: str | None = None,
    threshold: float = OVERCROWDING_ALERT_THRESHOLD,
    limit: int = 50,
) -> list[OvercrowdingAlert]:
    """Route segments whose simulated occupancy exceeds the alert threshold.

    The records are grouped per (route, segment, date, hour) so that one
    alert describes one specific hour of one specific segment.
    """
    stmt = (
        select(
            DemandRecord.route_id,
            DemandRecord.route_name,
            DemandRecord.mode,
            DemandRecord.segment_id,
            DemandRecord.origin_name,
            DemandRecord.dest_name,
            DemandRecord.date,
            DemandRecord.hour,
            func.avg(DemandRecord.passenger_count),
            func.avg(DemandRecord.occupancy_pct),
            func.max(DemandRecord.occupancy_pct),
            func.count(DemandRecord.id),
        )
        .where(DemandRecord.occupancy_pct >= threshold * 100.0)
        .group_by(
            DemandRecord.route_id,
            DemandRecord.route_name,
            DemandRecord.mode,
            DemandRecord.segment_id,
            DemandRecord.origin_name,
            DemandRecord.dest_name,
            DemandRecord.date,
            DemandRecord.hour,
        )
        .order_by(
            func.avg(DemandRecord.occupancy_pct).desc(),
            func.avg(DemandRecord.passenger_count).desc(),
        )
        .limit(limit)
    )
    if mode:
        stmt = stmt.where(DemandRecord.mode == mode)
    if date_filter:
        stmt = stmt.where(DemandRecord.date == date_filter)

    alerts: list[OvercrowdingAlert] = []
    for row in session.execute(stmt):
        (
            route_id, route_name, row_mode, segment_id, origin_name, dest_name,
            row_date, hour, mean_pax, mean_occ, peak_occ, affected,
        ) = row
        severity = "critical" if float(mean_occ) >= CROWD_HIGH_MAX * 100 else "warning"
        alerts.append(
            OvercrowdingAlert(
                route_id=route_id,
                route_name=route_name,
                mode=row_mode,
                segment_id=segment_id,
                origin_name=origin_name,
                dest_name=dest_name,
                date=row_date,
                hour=int(hour),
                mean_passengers=round(float(mean_pax or 0.0), 1),
                mean_occupancy_pct=round(float(mean_occ or 0.0), 2),
                peak_occupancy_pct=round(float(peak_occ or 0.0), 2),
                crowd_level=crowd_level_for(float(mean_occ or 0.0) / 100.0),
                severity=severity,
                affected_records=int(affected or 0),
            )
        )
    return alerts


# --------------------------------------------------------------------------
# Hourly profile
# --------------------------------------------------------------------------
def hourly_profile(
    session: Session,
    route_id: str,
    on_date: str | None = None,
    mode: str | None = None,
) -> list[HourlyPoint]:
    """Mean simulated demand per hour for a route (or for the whole network)."""
    stmt = select(
        DemandRecord.hour,
        func.avg(DemandRecord.passenger_count),
        func.avg(DemandRecord.occupancy_pct),
        func.max(DemandRecord.passenger_count),
        func.count(DemandRecord.id),
    ).group_by(DemandRecord.hour)

    if route_id:
        stmt = stmt.where(DemandRecord.route_id == route_id)
    if mode:
        stmt = stmt.where(DemandRecord.mode == mode)
    if on_date:
        stmt = stmt.where(DemandRecord.date == on_date)

    by_hour = {int(h): (float(mp or 0), float(mo or 0), int(mx or 0), int(c or 0))
               for h, mp, mo, mx, c in session.execute(stmt)}

    points: list[HourlyPoint] = []
    for hour in range(24):
        mean_pax, mean_occ, max_pax, count = by_hour.get(hour, (0.0, 0.0, 0, 0))
        points.append(
            HourlyPoint(
                hour=hour,
                mean_passengers=round(mean_pax, 1),
                mean_occupancy_pct=round(mean_occ, 2),
                max_passengers=max_pax,
                crowd_level=crowd_level_for(mean_occ / 100.0),
                records=count,
            )
        )
    return points


# --------------------------------------------------------------------------
# Authority dashboard
# --------------------------------------------------------------------------
def mode_comparison(session: Session) -> list[ModeComparison]:
    """Bus vs metro comparison over the whole simulated period.

    The **primary** metrics are the ones that are comparable between the two
    modes: the mean occupancy (a share of the capacity offered) and the
    passengers per vehicle.  The absolute passenger totals are kept as
    secondary information, because a metro vehicle seats 320 and a bus 48, so
    raw passenger counts are not comparable.
    """
    total_all = int(
        session.scalar(select(func.sum(DemandRecord.passenger_count))) or 0
    )
    total_records_all = int(
        session.scalar(select(func.count()).select_from(DemandRecord)) or 0
    )
    result: list[ModeComparison] = []
    for mode in ("metro", "bus"):
        row = session.execute(
            select(
                func.sum(DemandRecord.passenger_count),
                func.avg(DemandRecord.passenger_count),
                func.avg(DemandRecord.occupancy_pct),
                func.count(DemandRecord.id),
                _count_true(DemandRecord.is_overcrowded),
                func.avg(DemandRecord.service_frequency),
                func.avg(DemandRecord.hourly_capacity),
            ).where(DemandRecord.mode == mode)
        ).one()
        total, mean_pax, mean_occ, records, overcrowded, mean_freq, mean_cap = row
        total = int(total or 0)
        records = int(records or 0)
        mean_freq = float(mean_freq or 0.0)
        mean_cap = float(mean_cap or 0.0)
        result.append(
            ModeComparison(
                mode=mode,
                total_passengers=total,
                mean_passengers=round(float(mean_pax or 0.0), 1),
                mean_occupancy_pct=round(float(mean_occ or 0.0), 2),
                routes=count_routes(session, mode),
                records=records,
                share_pct=round(100.0 * total / total_all, 2) if total_all else 0.0,
                overcrowded_records=int(overcrowded or 0),
                overcrowded_share_pct=(
                    round(100.0 * int(overcrowded or 0) / records, 2) if records else 0.0
                ),
                # Passengers per vehicle per hour: the only absolute figure
                # that can be compared between a 320-seat and a 48-seat vehicle.
                passengers_per_vehicle=(
                    round(float(mean_pax or 0.0) / mean_freq, 1) if mean_freq else 0.0
                ),
                mean_vehicles_per_hour=round(mean_freq, 2),
                mean_hourly_capacity=round(mean_cap, 1),
                share_of_records_pct=(
                    round(100.0 * records / total_records_all, 2)
                    if total_records_all
                    else 0.0
                ),
            )
        )
    return result


def route_analytics(session: Session, mode: str | None = None) -> list[RouteAnalytics]:
    """Per-route aggregates including the busiest hour and segment."""
    stmt = select(Route.id, Route.name, Route.mode, Route.vehicle_capacity)
    if mode:
        stmt = stmt.where(Route.mode == mode)
    routes = session.execute(stmt).all()
    analytics: list[RouteAnalytics] = []
    for route_id, route_name, mode, vehicle_capacity in routes:
        agg = session.execute(
            select(
                func.sum(DemandRecord.passenger_count),
                func.avg(DemandRecord.passenger_count),
                func.avg(DemandRecord.occupancy_pct),
                func.count(DemandRecord.id),
                _count_true(DemandRecord.is_overcrowded),
            ).where(DemandRecord.route_id == route_id)
        ).one()
        total, mean_pax, mean_occ, records, overcrowded = agg
        records = int(records or 0)

        peak_row = session.execute(
            select(
                DemandRecord.hour,
                func.avg(DemandRecord.passenger_count),
                func.avg(DemandRecord.occupancy_pct),
                func.avg(DemandRecord.service_frequency),
            )
            .where(DemandRecord.route_id == route_id)
            .group_by(DemandRecord.hour)
            .order_by(func.avg(DemandRecord.passenger_count).desc())
            .limit(1)
        ).first()
        peak_hour = int(peak_row[0]) if peak_row else 0
        peak_passengers = float(peak_row[1]) if peak_row else 0.0
        peak_occ = float(peak_row[2]) if peak_row else 0.0
        peak_freq = float(peak_row[3]) if peak_row else 0.0

        busiest = session.execute(
            select(
                DemandRecord.segment_id,
                DemandRecord.origin_name,
                DemandRecord.dest_name,
                func.avg(DemandRecord.passenger_count),
            )
            .where(DemandRecord.route_id == route_id)
            .group_by(
                DemandRecord.segment_id,
                DemandRecord.origin_name,
                DemandRecord.dest_name,
            )
            .order_by(func.avg(DemandRecord.passenger_count).desc())
            .limit(1)
        ).first()

        overcrowded = int(overcrowded or 0)
        analytics.append(
            RouteAnalytics(
                route_id=route_id,
                route_name=route_name,
                mode=mode,
                total_passengers=int(total or 0),
                mean_passengers=round(float(mean_pax or 0.0), 1),
                peak_hour=peak_hour,
                peak_passengers=round(peak_passengers, 1),
                mean_occupancy_pct=round(float(mean_occ or 0.0), 2),
                overcrowded_records=overcrowded,
                busiest_segment=busiest[0] if busiest else "",
                overcrowded_share_pct=(
                    round(100.0 * overcrowded / records, 2) if records else 0.0
                ),
                busiest_segment_names=(
                    f"{busiest[1]} → {busiest[2]}" if busiest else ""
                ),
                peak_load_per_vehicle=(
                    round(peak_passengers / peak_freq, 1) if peak_freq else 0.0
                ),
                vehicle_capacity=int(vehicle_capacity or 0),
                peak_occupancy_pct=round(peak_occ, 2),
            )
        )
    analytics.sort(key=lambda item: item.total_passengers, reverse=True)
    return analytics


def hourly_analytics(session: Session, mode: str | None = None) -> list[HourlyAnalytics]:
    """Network wide demand per hour, split by transport mode.

    When ``mode`` is given, only the records of that mode are aggregated, so
    the Metro and the Bus tab of the authority dashboard show their own
    profile.
    """
    stmt = select(
        DemandRecord.hour,
        DemandRecord.mode,
        func.avg(DemandRecord.passenger_count),
        func.avg(DemandRecord.occupancy_pct),
        func.count(DemandRecord.id),
        func.sum(
            func.cast(
                DemandRecord.occupancy_pct >= OVERCROWDING_ALERT_THRESHOLD * 100.0,
                Integer,
            )
        ),
    ).group_by(DemandRecord.hour, DemandRecord.mode)
    if mode:
        stmt = stmt.where(DemandRecord.mode == mode)
    rows = session.execute(stmt).all()

    table: dict[int, dict] = {
        hour: {"total": [], "metro": [], "bus": [], "occ": [], "over": 0, "count": 0}
        for hour in range(24)
    }
    for hour, row_mode, mean_pax, mean_occ, count, over in rows:
        table[int(hour)]["total"].append(float(mean_pax or 0.0))
        table[int(hour)][row_mode].append(float(mean_pax or 0.0))
        table[int(hour)]["occ"].append(float(mean_occ or 0.0))
        table[int(hour)]["over"] += int(over or 0)
        table[int(hour)]["count"] += int(count or 0)

    analytics: list[HourlyAnalytics] = []
    for hour in range(24):
        entry = table[hour]
        total = sum(entry["total"]) / len(entry["total"]) if entry["total"] else 0.0
        occ = sum(entry["occ"]) / len(entry["occ"]) if entry["occ"] else 0.0
        analytics.append(
            HourlyAnalytics(
                hour=hour,
                mean_passengers=round(total, 1),
                mean_occupancy_pct=round(occ, 2),
                metro_passengers=round(
                    sum(entry["metro"]) / len(entry["metro"]) if entry["metro"] else 0.0, 1
                ),
                bus_passengers=round(
                    sum(entry["bus"]) / len(entry["bus"]) if entry["bus"] else 0.0, 1
                ),
                crowd_level=crowd_level_for(occ / 100.0),
                overcrowded_share_pct=(
                    round(100.0 * entry["over"] / entry["count"], 2) if entry["count"] else 0.0
                ),
                observations=entry["count"],
            )
        )
    return analytics


# --------------------------------------------------------------------------
# Service frequency recommendations
# --------------------------------------------------------------------------
def weekday_weekend_profile(
    session: Session, mode: str | None = None
) -> list[dict]:
    """Mean occupancy per hour, split into a weekday and a weekend line.

    This is the series behind the "weekday vs weekend" chart of the Metro and
    the Bus tab.  The unit is the mean occupancy of the sampled
    route-stretch-hours, in percent of the hourly capacity.
    """
    stmt = select(
        DemandRecord.hour,
        DemandRecord.is_weekend,
        func.avg(DemandRecord.occupancy_pct),
        func.avg(DemandRecord.passenger_count),
        func.count(DemandRecord.id),
    ).group_by(DemandRecord.hour, DemandRecord.is_weekend)
    if mode:
        stmt = stmt.where(DemandRecord.mode == mode)
    rows = session.execute(stmt).all()

    weekday: dict[int, tuple[float, float, int]] = {}
    weekend: dict[int, tuple[float, float, int]] = {}
    for hour, is_weekend, mean_occ, mean_pax, count in rows:
        target = weekend if is_weekend else weekday
        target[int(hour)] = (
            float(mean_occ or 0.0),
            float(mean_pax or 0.0),
            int(count or 0),
        )

    profile: list[dict] = []
    for hour in range(24):
        wd = weekday.get(hour, (0.0, 0.0, 0))
        we = weekend.get(hour, (0.0, 0.0, 0))
        profile.append(
            {
                "hour": hour,
                "weekday_occupancy_pct": round(wd[0], 2),
                "weekend_occupancy_pct": round(we[0], 2),
                "weekday_passengers": round(wd[1], 1),
                "weekend_passengers": round(we[1], 1),
                "weekday_records": wd[2],
                "weekend_records": we[2],
            }
        )
    return profile


def service_recommendations(
    session: Session, limit: int = 12, mode: str | None = None
) -> list[ServiceRecommendation]:
    """Suggest timetable changes for the route-hour combinations that need it.

    The rule is deliberately simple and explainable:

    * a segment whose simulated occupancy is above 80 % is recommended to get
      **one extra vehicle per hour**,
    * a segment that stays below 40 % of the capacity is recommended to
      **drop one vehicle per hour** (never below one).

    These are recommendations, not optimal decisions.
    """
    from navacity_core.config import service_frequency_for

    recommendations: list[ServiceRecommendation] = []
    stmt = (
        select(
            DemandRecord.route_id,
            DemandRecord.route_name,
            DemandRecord.mode,
            DemandRecord.hour,
            DemandRecord.segment_id,
            func.avg(DemandRecord.occupancy_pct),
            func.max(DemandRecord.occupancy_pct),
            func.count(DemandRecord.id),
        )
        .group_by(
            DemandRecord.route_id,
            DemandRecord.route_name,
            DemandRecord.mode,
            DemandRecord.hour,
            DemandRecord.segment_id,
        )
        .order_by(func.avg(DemandRecord.occupancy_pct).desc())
    )
    if mode:
        stmt = stmt.where(DemandRecord.mode == mode)
    rows = session.execute(stmt).all()

    route_meta = {
        route.id: route for route in session.execute(select(Route)).scalars()
    }
    # The human readable name of every stretch, so that the planner does not
    # have to decode a segment id.
    segment_names: dict[str, str] = {}
    for seg_id, origin, dest in session.execute(
        select(
            DemandRecord.segment_id,
            DemandRecord.origin_name,
            DemandRecord.dest_name,
        ).distinct()
    ):
        segment_names[seg_id] = f"{origin} → {dest}"
    seen: set[tuple[str, int]] = set()

    for (route_id, route_name, mode, hour, segment_id,
         mean_occ, peak_occ, records) in rows:
        key = (route_id, int(hour))
        if key in seen:
            continue
        route = route_meta.get(route_id)
        if route is None:
            continue
        mean_occ = float(mean_occ or 0.0)
        if mean_occ < OVERCROWDING_ALERT_THRESHOLD * 100.0 and mean_occ >= CROWD_LOW_MAX * 100.0:
            continue
        if mean_occ >= OVERCROWDING_ALERT_THRESHOLD * 100.0:
            change = 1
            rule = (
                f"Add 1 vehicle per hour when the mean occupancy of a "
                f"route-stretch is at or above "
                f"{OVERCROWDING_ALERT_THRESHOLD * 100:.0f}% (the 40-85% band is "
                f"the target range)."
            )
            reason = (
                f"Simulated occupancy averages {mean_occ:.1f}% on {segment_id} at "
                f"{int(hour):02d}:00, above the "
                f"{OVERCROWDING_ALERT_THRESHOLD * 100:.0f}% alert threshold "
                f"(peak {float(peak_occ or 0.0):.1f}%)."
            )
            confidence = (
                "high"
                if float(peak_occ or 0.0) >= CROWD_HIGH_MAX * 100
                else "medium"
            )
        else:
            change = -1
            rule = (
                f"Remove 1 vehicle per hour when the mean occupancy of a "
                f"route-stretch stays below {CROWD_LOW_MAX * 100:.0f}% "
                f"(never below 1 vehicle per hour)."
            )
            reason = (
                f"Simulated occupancy averages {mean_occ:.1f}% on {segment_id} at "
                f"{int(hour):02d}:00, well below the {CROWD_LOW_MAX * 100:.0f}% "
                f"threshold, so one vehicle per hour could be redeployed."
            )
            confidence = "medium"

        current = service_frequency_for(mode, int(hour), "weekday", route.base_frequency)
        recommended = max(1, current + change)
        if recommended == current:
            continue
        seen.add(key)
        recommendations.append(
            ServiceRecommendation(
                route_id=route_id,
                route_name=route_name,
                mode=mode,
                hour=int(hour),
                current_frequency=current,
                recommended_frequency=recommended,
                change=recommended - current,
                reason=reason,
                confidence=confidence,
                disclaimer=RECOMMENDATION_DISCLAIMER,
                rule=rule,
                segment_id=segment_id,
                segment_names=segment_names.get(segment_id, ""),
            )
        )
        if len(recommendations) >= limit:
            break
    return recommendations


def authority_stats(
    session: Session, on_date: str | None = None, mode: str | None = None
) -> AuthorityStatsResponse:
    """Everything the transport-authority dashboard needs, in one payload.

    When ``mode`` is given the payload is restricted to that transport mode,
    so the Metro and the Bus tab of the dashboard are served by the same
    endpoint with the same layout.
    """
    records_stmt = select(func.count()).select_from(DemandRecord)
    passengers_stmt = select(func.sum(DemandRecord.passenger_count))
    occ_stmt = select(func.avg(DemandRecord.occupancy_pct))
    over_stmt = select(func.count(DemandRecord.id)).where(
        DemandRecord.occupancy_pct >= OVERCROWDING_ALERT_THRESHOLD * 100.0
    )
    if mode:
        records_stmt = records_stmt.where(DemandRecord.mode == mode)
        passengers_stmt = passengers_stmt.where(DemandRecord.mode == mode)
        occ_stmt = occ_stmt.where(DemandRecord.mode == mode)
        over_stmt = over_stmt.where(DemandRecord.mode == mode)

    total_records = int(session.scalar(records_stmt) or 0)
    total_passengers = int(session.scalar(passengers_stmt) or 0)
    avg_occ = float(session.scalar(occ_stmt) or 0.0)
    overcrowded = int(session.scalar(over_stmt) or 0)
    min_date, max_date = dataset_date_range(session)

    comparisons = mode_comparison(session)
    analytics = route_analytics(session, mode)
    hourly = hourly_analytics(session, mode)
    recommendations = service_recommendations(session, mode=mode)
    profile = weekday_weekend_profile(session, mode)

    peak_hours = [
        item.hour
        for item in sorted(hourly, key=lambda h: h.mean_passengers, reverse=True)[:3]
    ]
    over_share = 100.0 * overcrowded / total_records if total_records else 0.0

    scope = "the simulated network" if not mode else f"the {mode} network"
    kpis = [
        KpiCard(
            key="total_routes",
            label="Total routes",
            value=count_routes(session, mode),
            unit="routes",
            detail=f"Routes in {scope}",
        ),
        KpiCard(
            key="total_stations",
            label="Metro stations",
            value=count_metro_served_places(session),
            unit="stations",
            detail="Places served by at least one metro line",
        ),
        KpiCard(
            key="total_stops",
            label="Bus stops",
            value=count_bus_served_places(session),
            unit="stops",
            detail="Places served by at least one bus route",
        ),
        KpiCard(
            key="total_passengers",
            label="Simulated passengers",
            value=total_passengers,
            unit="passengers",
            detail=(
                f"Sum over {total_records:,} simulated observations "
                f"(4 per route-stretch per day)"
            ),
        ),
        KpiCard(
            key="avg_occupancy",
            label="Average occupancy",
            value=round(avg_occ, 2),
            unit="%",
            detail="Mean of the simulated occupancy",
        ),
        KpiCard(
            key="overcrowded_records",
            label="Overcrowded observations",
            value=overcrowded,
            unit="records",
            detail=(
                f"{over_share:.2f}% of the observations are at or above "
                f"{OVERCROWDING_ALERT_THRESHOLD * 100:.0f}% occupancy"
            ),
        ),
    ]

    return AuthorityStatsResponse(
        generated_for=on_date or max_date or "entire simulated period",
        data_notice=DATA_NOTICE,
        total_routes=count_routes(session, mode),
        total_stations=count_metro_served_places(session),
        total_stops=count_bus_served_places(session),
        total_records=total_records,
        total_passengers=total_passengers,
        average_occupancy_pct=round(avg_occ, 2),
        overcrowded_records=overcrowded,
        mode=mode,
        kpis=kpis,
        mode_comparison=comparisons,
        route_analytics=analytics,
        hourly_analytics=hourly,
        weekday_weekend_profile=profile,
        peak_hours=peak_hours,
        recommendations=recommendations,
        data_period={
            "start": min_date,
            "end": max_date,
            "granularity": (
                "4 sampled hours per route-stretch per day "
                "(not a complete hourly series)"
            ),
            "records": total_records,
        },
    )
