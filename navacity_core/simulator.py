"""Rule-based simulator that produces the SIMULATED NavaCity dataset.

Design
------
Demand is generated in two steps for every (segment, date, hour) triple:

1. An *occupancy target* is derived from the context (time of day, day type,
   weather, traffic, holidays, special events, route popularity).  This uses
   the hand tuned hour-of-day profiles in :mod:`navacity_core.config`.
2. The *passenger demand* is the occupancy target multiplied by the capacity
   the planned service offers in that hour
   (``vehicle_capacity x service_frequency``).  More frequent service attracts
   more riders, which is why the target scales with the timetable.

Finally a log-normal noise term is applied so the data is not a
deterministic function of the features and the ML models have something real
to learn (and a realistic error level to report).

No target leakage
-----------------
Only quantities that are known *before* the trip happens are used as inputs:
the timetable, the calendar, the weather forecast and the traffic forecast.
Actual passenger counts and the resulting occupancy are never inputs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from .config import (
    BASE_OCCUPANCY,
    CROWD_LEVELS,
    OVERCROWDING_ALERT_THRESHOLD,
    RANDOM_SEED,
    SIM_END_DATE,
    SIM_START_DATE,
    TRAFFIC_OCCUPANCY_FACTOR,
    TRAFFIC_TRAVEL_TIME_FACTOR,
    WEATHER_OCCUPANCY_FACTOR,
    WEATHER_TRAFFIC_FACTOR,
    crowd_level_for,
    day_type_for,
    occupancy_profile_for,
    service_frequency_for,
)
from .events import events_by_date, holiday_name
from .network import (
    MODE_WAIT_PER_HEADWAY,
    ROUTE_POPULARITY,
    VEHICLE_CAPACITY,
    build_network,
)

# --------------------------------------------------------------------------
# Contextual profiles
# --------------------------------------------------------------------------
# Share of the whole route's hourly demand carried by each segment.
# Central segments carry more than the outer ones (classic taper).
def _segment_taper(num_segments: int, mode: str) -> np.ndarray:
    idx = np.arange(num_segments)
    amplitude = 0.80 if mode == "metro" else 0.45
    weights = 1.0 + amplitude * np.sin(np.pi * (idx + 0.5) / max(1, num_segments))
    return weights / weights.sum()


# Probability of a wet day per month (monsoon builds up towards June).
_RAIN_PROBABILITY = {
    1: 0.10, 2: 0.08, 3: 0.14, 4: 0.24, 5: 0.34, 6: 0.55,
}
_FOG_PROBABILITY = {1: 0.12, 2: 0.10, 3: 0.06, 4: 0.03, 5: 0.02, 6: 0.01}

# Slow seasonal growth of the network over the six simulated months.
_SEASONAL_GROWTH_PER_DAY = 0.00055

# Noise level of the multiplicative log-normal term.
_DEMAND_NOISE_SIGMA = 0.13
_OCCUPANCY_NOISE_SIGMA = 0.055


@dataclass
class DailyContext:
    """Weather / calendar context of a single simulated day."""

    day: date
    weather_by_hour: list[str]
    is_holiday: bool
    holiday: str | None
    events: list[dict]


def _build_daily_context(day: date, rng: np.random.Generator, event_index: dict) -> DailyContext:
    """Pre-compute the weather and calendar context of one day.

    The weather is resolved per day (not per segment) so that every segment
    of the city experiences the same day, which is what a real city does.
    """
    month = day.month
    holiday = holiday_name(day)
    is_holiday = holiday is not None

    rain_p = _RAIN_PROBABILITY.get(month, 0.2)
    fog_p = _FOG_PROBABILITY.get(month, 0.05)
    is_weekend = day.weekday() >= 5

    # A wet day lasts for part of the day; mornings are drier than evenings.
    if rng.random() < rain_p:
        heavy = rng.random() < 0.35
        rain_start = int(rng.integers(6, 20))
        rain_end = min(23, rain_start + int(rng.integers(3, 9)))
    else:
        heavy = False
        rain_start, rain_end = -1, -1

    fog_day = rng.random() < fog_p
    fog_hours = set(range(int(rng.integers(4, 8))) if not is_weekend else range(0, 1))

    weather_by_hour: list[str] = []
    for hour in range(24):
        if fog_day and hour in fog_hours:
            weather_by_hour.append("fog")
        elif rain_start <= hour <= rain_end:
            weather_by_hour.append("heavy_rain" if heavy else "light_rain")
        elif rng.random() < 0.35:
            weather_by_hour.append("cloudy")
        else:
            weather_by_hour.append("clear")

    return DailyContext(
        day=day,
        weather_by_hour=weather_by_hour,
        is_holiday=is_holiday,
        holiday=holiday,
        events=event_index.get(day, []),
    )


# --------------------------------------------------------------------------
# Traffic model
# --------------------------------------------------------------------------
_WEEKDAY_TRAFFIC = {
    0: 0.10, 1: 0.06, 2: 0.05, 3: 0.05, 4: 0.10, 5: 0.20,
    6: 0.45, 7: 0.75, 8: 0.95, 9: 0.80, 10: 0.55, 11: 0.50,
    12: 0.55, 13: 0.50, 14: 0.48, 15: 0.55, 16: 0.70,
    17: 0.90, 18: 1.00, 19: 0.85, 20: 0.60, 21: 0.40,
    22: 0.25, 23: 0.15,
}
_WEEKEND_TRAFFIC = {
    0: 0.12, 1: 0.08, 2: 0.06, 3: 0.05, 4: 0.07, 5: 0.10,
    6: 0.15, 7: 0.22, 8: 0.30, 9: 0.35, 10: 0.45, 11: 0.50,
    12: 0.55, 13: 0.55, 14: 0.52, 15: 0.50, 16: 0.48,
    17: 0.50, 18: 0.52, 19: 0.50, 20: 0.45, 21: 0.35,
    22: 0.25, 23: 0.18,
}


def _traffic_level_for(
    hour: int, day_type: str, weather: str, rng: np.random.Generator, growth: float
) -> str:
    """Bucket the congestion score into a traffic level."""
    base = (_WEEKDAY_TRAFFIC if day_type == "weekday" else _WEEKEND_TRAFFIC)[hour]
    score = base * (1.0 + growth) * WEATHER_TRAFFIC_FACTOR[weather]
    score += float(rng.normal(0.0, 0.10))
    score = min(1.25, max(0.0, score))

    if score >= 0.92:
        return "severe"
    if score >= 0.68:
        return "heavy"
    if score >= 0.38:
        return "moderate"
    return "light"


# --------------------------------------------------------------------------
# Event effect
# --------------------------------------------------------------------------
def _place_event_multiplier(
    events: list[dict], hour: int, place_names: set[str], route_id: str
) -> float:
    """Extra demand multiplier caused by a special event."""
    multiplier = 1.0
    for event in events:
        if not (event["hour_start"] <= hour <= event["hour_end"]):
            continue
        hits = place_names & set(event["places"])
        if hits:
            multiplier *= 1.0 + (event["attraction"] - 1.0) * 1.30
        elif route_id in event["routes"]:
            multiplier *= event["attraction"]
    return multiplier


# --------------------------------------------------------------------------
# Main generation entry point
# --------------------------------------------------------------------------
def generate_dataset(
    start_date: date = SIM_START_DATE,
    end_date: date = SIM_END_DATE,
    seed: int = RANDOM_SEED,
    samples_per_day: int = 4,
) -> pd.DataFrame:
    """Generate the SIMULATED NavaCity hourly demand dataset.

    Parameters
    ----------
    start_date, end_date:
        Inclusive calendar window of the simulation.
    seed:
        Seed of the random generator - the same seed always produces the
        same dataset.
    samples_per_day:
        Number of hourly observations generated per route-segment and day.
        Two of them are always the commuter peaks (08:00 and 18:00).
    """
    rng = np.random.default_rng(seed)
    network = build_network()
    segments = network["segments"]
    event_index = events_by_date()

    # Pre-compute the taper of every route.
    taper_cache: dict[str, np.ndarray] = {}
    route_segment_count: dict[str, int] = {}
    for seg in segments:
        route_segment_count[seg["route_id"]] = (
            route_segment_count.get(seg["route_id"], 0) + 1
        )
    for route_id, count in route_segment_count.items():
        mode = "metro" if route_id.startswith("M") else "bus"
        taper_cache[route_id] = _segment_taper(count, mode)

    # The set of place names that serve each route.
    route_places: dict[str, set[str]] = {}
    for seg in segments:
        route_places.setdefault(seg["route_id"], set()).update(
            {seg["origin_name"], seg["dest_name"]}
        )

    base_frequency = {}
    for line in network["metro_lines"]:
        base_frequency[line["id"]] = line["base_frequency"]
    for route in network["bus_routes"]:
        base_frequency[route["id"]] = route["base_frequency"]

    rows: list[dict] = []
    total_days = (end_date - start_date).days + 1

    for day_offset in range(total_days):
        day = start_date + timedelta(days=day_offset)
        context = _build_daily_context(day, rng, event_index)
        is_weekend = day.weekday() >= 5
        day_type = day_type_for(is_weekend, context.is_holiday)
        growth = _SEASONAL_GROWTH_PER_DAY * day_offset

        # Which hours are sampled on this day.
        hours = [8, 18]
        extra = max(0, samples_per_day - len(hours))
        if extra:
            candidates = [h for h in range(24) if h not in hours]
            hours += list(rng.choice(candidates, size=extra, replace=False))
        hours = sorted(int(h) for h in hours)

        for seg in segments:
            route_id = seg["route_id"]
            mode = seg["mode"]
            seg_index = seg["segment_index"]
            taper = taper_cache[route_id]
            # Relative load of this segment compared with the average segment
            # of the route (outer segments are less busy than central ones).
            seg_factor = float(taper[seg_index] / taper.mean())
            n_route_segments = route_segment_count[route_id]

            for hour in hours:
                weather = context.weather_by_hour[hour]
                traffic = _traffic_level_for(hour, day_type, weather, rng, growth)

                # ---- Timetable -------------------------------------------
                freq = service_frequency_for(
                    mode, hour, day_type, base_frequency[route_id]
                )
                capacity = VEHICLE_CAPACITY[mode]
                hourly_capacity = capacity * freq

                # ---- Occupancy target -----------------------------------
                occ_profile = occupancy_profile_for(day_type)
                occupancy = BASE_OCCUPANCY[mode] * occ_profile[hour]
                occupancy *= ROUTE_POPULARITY[route_id]
                occupancy *= WEATHER_OCCUPANCY_FACTOR[weather]
                occupancy *= TRAFFIC_OCCUPANCY_FACTOR[traffic]
                if context.is_holiday:
                    occupancy *= 0.72
                if day_type == "weekend":
                    occupancy *= 0.90 if mode == "metro" else 0.86
                    if hour <= 5:
                        occupancy *= 0.75
                occupancy *= 1.0 + growth
                occupancy *= seg_factor
                occupancy *= _place_event_multiplier(
                    context.events, hour, route_places[route_id], route_id
                )
                occupancy *= float(
                    rng.lognormal(
                        mean=-0.5 * _OCCUPANCY_NOISE_SIGMA**2,
                        sigma=_OCCUPANCY_NOISE_SIGMA,
                    )
                )
                occupancy = float(np.clip(occupancy, 0.02, 1.25))

                # ---- Passenger demand -----------------------------------
                demand = hourly_capacity * occupancy
                demand *= float(
                    rng.lognormal(
                        mean=-0.5 * _DEMAND_NOISE_SIGMA**2,
                        sigma=_DEMAND_NOISE_SIGMA,
                    )
                )
                demand = float(max(0.0, round(demand)))

                # ---- Waiting time ----------------------------------------
                headway = 60.0 / freq
                wait = headway * MODE_WAIT_PER_HEADWAY[mode]
                if occupancy > 0.85:
                    wait += 1.2
                if traffic in ("heavy", "severe") and mode == "bus":
                    wait += 0.8
                wait += float(rng.normal(0.0, 0.35))
                wait = float(max(0.5, round(wait, 1)))

                # ---- Travel time -----------------------------------------
                travel = seg["travel_minutes"] * (
                    1.0 + 0.06 * (seg_index / max(1, n_route_segments - 1))
                )
                if mode == "bus":
                    travel *= TRAFFIC_TRAVEL_TIME_FACTOR[traffic]
                travel = float(round(travel, 1))

                crowd_level = crowd_level_for(occupancy)
                special = any(
                    event["hour_start"] <= hour <= event["hour_end"]
                    and (
                        seg["origin_name"] in event["places"]
                        or seg["dest_name"] in event["places"]
                        or route_id in event["routes"]
                    )
                    for event in context.events
                )

                rows.append(
                    {
                        "timestamp": datetime(
                            day.year, day.month, day.day, hour
                        ).isoformat(timespec="seconds"),
                        "date": day.isoformat(),
                        "hour": hour,
                        "day_of_week": day.weekday(),
                        "day_name": day.strftime("%A"),
                        "is_weekend": bool(is_weekend),
                        "is_holiday": bool(context.is_holiday),
                        # A readable sentinel instead of an empty cell: pandas
                        # reads an empty cell back as NaN (and also treats the
                        # literal "None" as NaN), which would make the dataset
                        # look like it has missing values.
                        "holiday_name": context.holiday or "Not a holiday",
                        "day_type": day_type,
                        "mode": mode,
                        "route_id": route_id,
                        "route_name": seg["route_name"],
                        "segment_id": seg["segment_id"],
                        "origin_id": seg["origin_id"],
                        "origin_name": seg["origin_name"],
                        "dest_id": seg["dest_id"],
                        "dest_name": seg["dest_name"],
                        "passenger_count": int(demand),
                        "vehicle_capacity": capacity,
                        "service_frequency": int(freq),
                        "hourly_capacity": int(hourly_capacity),
                        "occupancy_pct": round(occupancy * 100.0, 2),
                        "crowd_level": crowd_level,
                        "weather": weather,
                        "traffic_level": traffic,
                        "special_event": bool(special),
                        "waiting_time_min": wait,
                        "travel_time_min": travel,
                        "is_overcrowded": bool(
                            occupancy >= OVERCROWDING_ALERT_THRESHOLD
                        ),
                    }
                )

    df = pd.DataFrame(rows)
    df = df.sort_values(
        ["timestamp", "mode", "route_id", "segment_id"]
    ).reset_index(drop=True)
    return df
