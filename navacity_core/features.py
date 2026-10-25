"""Feature engineering shared by the training script and the backend.

This module is the single source of truth for the model's input format, so
the features produced at training time and at prediction time are always
identical.

Leakage policy
--------------
Only quantities that are known *before* the trip happens are used as model
inputs.  The following columns of the generated dataset are therefore
**excluded** and must never be passed to the model:

``passenger_count``    the prediction target
``occupancy_pct``      derived from the target
``crowd_level``        derived from the occupancy
``is_overcrowded``     derived from the occupancy
``waiting_time_min``   derived from the occupancy
``travel_time_min``    redundant with ``traffic_level`` and route geometry
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from .config import (
    PEAK_HOURS,
    SIM_END_DATE,
    SIM_START_DATE,
    day_type_for,
    service_frequency_for,
)
from .network import build_network

# --------------------------------------------------------------------------
# Feature definition
# --------------------------------------------------------------------------
NUMERIC_FEATURES: list[str] = [
    "hour",
    "day_of_week",
    "month_sin",
    "month_cos",
    "day_index",
    "is_weekend",
    "is_holiday",
    "is_peak_hour",
    "vehicle_capacity",
    "service_frequency",
    "hourly_capacity",
    "segment_index",
    "num_stops",
    "route_popularity",
]

CATEGORICAL_FEATURES: list[str] = [
    "mode",
    "route_id",
    "segment_id",
    "origin_id",
    "dest_id",
    "day_type",
    "weather",
    "traffic_level",
    "special_event",
]

FEATURE_COLUMNS: list[str] = NUMERIC_FEATURES + CATEGORICAL_FEATURES

TARGET_COLUMN = "passenger_count"

# Columns that must never be used as a model input.
LEAKY_COLUMNS: list[str] = [
    "passenger_count",
    "occupancy_pct",
    "crowd_level",
    "is_overcrowded",
    "waiting_time_min",
    "travel_time_min",
]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def is_peak_hour(hour: int) -> bool:
    """True for the two commuter peaks used by the simulator."""
    return int(hour) in PEAK_HOURS


# The first day of the simulated period.  The "day_index" feature counts the
# days since that date, which lets the model learn the slow seasonal growth of
# the network.  It is clipped to the simulated window so that a forecast far
# in the future cannot extrapolate a growth trend that was never observed.
SIM_EPOCH = SIM_START_DATE
SIM_DAY_COUNT = (SIM_END_DATE - SIM_START_DATE).days + 1


def calendar_features(on_date: date) -> dict:
    """Cyclical month encoding plus a clipped day index.

    The month is encoded as sin/cos so that December and January are close to
    each other instead of being at the opposite end of a numeric range, and
    the day index is clipped to the length of the simulated period so the
    model cannot extrapolate a growth trend beyond the observed data.
    """
    month = int(on_date.month)
    angle = 2.0 * np.pi * (month - 1) / 12.0
    day_index = (on_date - SIM_EPOCH).days
    return {
        "month_sin": float(np.sin(angle)),
        "month_cos": float(np.cos(angle)),
        "day_index": float(np.clip(day_index, 0, SIM_DAY_COUNT - 1)),
    }


def _network_index() -> dict:
    """Route / segment metadata used to build features."""
    network = build_network()
    routes: dict[str, dict] = {}
    for line in network["metro_lines"]:
        routes[line["id"]] = {
            "id": line["id"],
            "name": line["name"],
            "mode": "metro",
            "base_frequency": line["base_frequency"],
            "vehicle_capacity": line["vehicle_capacity"],
            "popularity": line["popularity"],
            "num_stops": len(line["stations"]),
        }
    for route in network["bus_routes"]:
        routes[route["id"]] = {
            "id": route["id"],
            "name": route["name"],
            "mode": "bus",
            "base_frequency": route["base_frequency"],
            "vehicle_capacity": route["vehicle_capacity"],
            "popularity": route["popularity"],
            "num_stops": len(route["stops"]),
        }
    segments: dict[str, dict] = {seg["segment_id"]: seg for seg in network["segments"]}
    return {"routes": routes, "segments": segments, "network": network}


def prepare_training_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Build the model input matrix from the raw generated dataset.

    The raw ``route_id``/``segment_id`` columns are kept, but the columns
    listed in :data:`LEAKY_COLUMNS` are dropped so that they can never leak
    into the model.
    """
    frame = df.copy()
    parsed = pd.to_datetime(frame["date"])
    frame["is_peak_hour"] = frame["hour"].apply(is_peak_hour)

    calendar = pd.DataFrame(
        [calendar_features(d.date()) for d in parsed], index=frame.index
    )
    frame["month_sin"] = calendar["month_sin"]
    frame["month_cos"] = calendar["month_cos"]
    frame["day_index"] = calendar["day_index"]

    index = _network_index()
    routes = index["routes"]
    segments = index["segments"]
    frame["route_popularity"] = frame["route_id"].map(
        lambda r: routes.get(r, {}).get("popularity", 1.0)
    )
    frame["num_stops"] = frame["route_id"].map(
        lambda r: routes.get(r, {}).get("num_stops", 1)
    )
    frame["segment_index"] = frame["segment_id"].map(
        lambda s: segments.get(s, {}).get("segment_index", 0)
    )
    frame["special_event"] = frame["special_event"].astype(str)
    return frame[FEATURE_COLUMNS].copy()


def build_prediction_features(
    route_id: str,
    hour: int,
    on_date: date,
    weather: str = "clear",
    traffic_level: str = "light",
    special_event: bool = False,
    segment_id: str | None = None,
    index: dict | None = None,
) -> pd.DataFrame:
    """Build a one-row feature matrix for a future prediction.

    Parameters
    ----------
    route_id:
        Metro line id (``M1`` ... ``M6``) or bus route id (``B01`` ... ``B10``).
    hour:
        Hour of the day, 0-23.
    on_date:
        Calendar day of the prediction.
    weather, traffic_level:
        Expected conditions.  The backend exposes these as optional inputs so
        the forecast can be run under different scenarios.
    special_event:
        Whether a special event is expected to affect the route.
    segment_id:
        Restrict the prediction to one segment of the route.  When omitted the
        busiest segment of the route is used, which is the segment the
        authority dashboard reports on.
    """
    idx = index if index is not None else _network_index()
    routes = idx["routes"]
    segments = idx["segments"]

    if route_id not in routes:
        raise KeyError(route_id)
    route = routes[route_id]

    if segment_id is None:
        candidates = [s for s in segments.values() if s["route_id"] == route_id]
        if not candidates:  # pragma: no cover - defensive
            raise KeyError(route_id)
        segment = max(candidates, key=lambda s: s["segment_index"])
    else:
        if segment_id not in segments:
            raise KeyError(segment_id)
        segment = segments[segment_id]
        if segment["route_id"] != route_id:
            raise ValueError(
                f"segment {segment_id} does not belong to route {route_id}"
            )

    day_type = day_type_for(on_date.weekday() >= 5, False)
    service_frequency = service_frequency_for(
        route["mode"], int(hour), day_type, route["base_frequency"]
    )
    capacity = route["vehicle_capacity"]

    row = {
        "hour": int(hour),
        "day_of_week": int(on_date.weekday()),
        **calendar_features(on_date),
        "is_weekend": bool(on_date.weekday() >= 5),
        "is_holiday": False,
        "is_peak_hour": is_peak_hour(int(hour)),
        "vehicle_capacity": capacity,
        "service_frequency": int(service_frequency),
        "hourly_capacity": int(capacity * service_frequency),
        "segment_index": int(segment["segment_index"]),
        "num_stops": int(route["num_stops"]),
        "route_popularity": float(route["popularity"]),
        "mode": route["mode"],
        "route_id": route["id"],
        "segment_id": segment["segment_id"],
        "origin_id": segment["origin_id"],
        "dest_id": segment["dest_id"],
        "day_type": day_type,
        "weather": weather,
        "traffic_level": traffic_level,
        "special_event": str(bool(special_event)),
    }
    return pd.DataFrame([row])[FEATURE_COLUMNS]


def busiest_segment_of(route_id: str, index: dict | None = None) -> dict | None:
    """Return the middle (busiest) segment of a route."""
    idx = index if index is not None else _network_index()
    candidates = [s for s in idx["segments"].values() if s["route_id"] == route_id]
    if not candidates:
        return None
    return max(candidates, key=lambda s: s["segment_index"])


# --------------------------------------------------------------------------
# Climatological defaults
# --------------------------------------------------------------------------
# Share of wet days per month used by the simulator (monsoon builds up).
_RAIN_PROBABILITY = {1: 0.10, 2: 0.08, 3: 0.14, 4: 0.24, 5: 0.34, 6: 0.55}


def default_weather_for(on_date: date, hour: int) -> str:
    """Climatological default weather used when the caller gives none.

    The simulator makes wet days more likely from March onwards; this helper
    returns the most likely (modal) condition so the default forecast is not
    systematically biased towards clear weather.
    """
    month = on_date.month
    rain_p = _RAIN_PROBABILITY.get(month, 0.2)
    if rain_p >= 0.45:
        return "light_rain"
    if rain_p >= 0.18:
        return "cloudy"
    return "clear"


def default_traffic_for(hour: int, on_date: date) -> str:
    """Climatological default traffic level for a given hour."""
    from .simulator import _WEEKDAY_TRAFFIC, _WEEKEND_TRAFFIC

    table = _WEEKEND_TRAFFIC if on_date.weekday() >= 5 else _WEEKDAY_TRAFFIC
    score = table[int(hour)]
    if score >= 0.92:
        return "severe"
    if score >= 0.68:
        return "heavy"
    if score >= 0.38:
        return "moderate"
    return "light"


def typical_occupancy_for(route_id: str, hour: int, on_date: date) -> float:
    """Typical (historical mean) occupancy of a route at a given hour.

    Used as a sanity anchor for the model's forecast and for the
    alternative-route suggestions.
    """
    from .config import (
        BASE_OCCUPANCY,
        TRAFFIC_OCCUPANCY_FACTOR,
        WEATHER_OCCUPANCY_FACTOR,
        occupancy_profile_for,
    )
    from .network import ROUTE_POPULARITY

    idx = _network_index()
    route = idx["routes"].get(route_id)
    if route is None:
        return 0.5
    day_type = day_type_for(on_date.weekday() >= 5, False)
    weather = default_weather_for(on_date, hour)
    traffic = default_traffic_for(hour, on_date)
    occ = BASE_OCCUPANCY[route["mode"]] * occupancy_profile_for(day_type)[int(hour)]
    occ *= ROUTE_POPULARITY[route_id]
    occ *= WEATHER_OCCUPANCY_FACTOR[weather]
    occ *= TRAFFIC_OCCUPANCY_FACTOR[traffic]
    if day_type == "weekend":
        occ *= 0.90 if route["mode"] == "metro" else 0.86
    return float(np.clip(occ, 0.02, 1.25))
