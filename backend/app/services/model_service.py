"""Model loading and prediction helpers for the NavaCity backend.

The trained pipeline is loaded once at start-up and kept in memory.  All
predictions go through this module so that the feature engineering stays
identical to the training time (both use :mod:`navacity_core.features`).
"""

from __future__ import annotations

import json
import threading
from datetime import date

import joblib

from navacity_core.config import crowd_level_for
from navacity_core.features import (
    build_prediction_features,
    default_traffic_for,
    default_weather_for,
)
from navacity_core.network import (
    MODE_WAIT_PER_HEADWAY,
    build_network,
    journey_ride_minutes,
    segment_between,
)

from ..config import settings

DATA_NOTICE = (
    "SIMULATED DATA - NavaCity is a fictional city. All figures are produced "
    "by a rule-based simulator and a model trained on that simulated data."
)

ASSUMPTIONS = (
    "Forecast assumes the published timetable for the requested hour, the "
    "climatological average weather/traffic for that month (or the values you "
    "supplied), and no unplanned disruption."
)


class ModelService:
    """Thin, thread-safe wrapper around the trained scikit-learn pipelines."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._bundle: dict | None = None
        self._metrics: dict | None = None
        self._network: dict | None = None
        self._network_index: dict | None = None
        self.load_error: str | None = None

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    def load(self) -> bool:
        """Load the model bundle, the metrics file and the network.

        Returns True when the model bundle could be loaded.  The API stays
        usable (the health check reports the problem) even when it fails.
        """
        try:
            if settings.model_bundle.exists():
                with self._lock:
                    self._bundle = joblib.load(settings.model_bundle)
            else:
                self.load_error = f"model bundle not found at {settings.model_bundle}"

            if settings.metrics_json.exists():
                with open(settings.metrics_json, encoding="utf-8") as fh:
                    self._metrics = json.load(fh)

            self._network = build_network()
            self._network_index = _index_network(self._network)
            return self._bundle is not None
        except Exception as exc:  # noqa: BLE001 - surfaced through /health
            self.load_error = f"{type(exc).__name__}: {exc}"
            return False

    @property
    def is_loaded(self) -> bool:
        return self._bundle is not None

    @property
    def bundle(self) -> dict:
        if self._bundle is None:
            raise RuntimeError(
                "Model bundle is not loaded. Run 'python ml\\train_model.py' first."
            )
        return self._bundle

    @property
    def metrics(self) -> dict:
        return self._metrics or {}

    @property
    def network(self) -> dict:
        if self._network is None:
            self._network = build_network()
        return self._network

    @property
    def index(self) -> dict:
        if self._network_index is None:
            self._network_index = _index_network(self.network)
        return self._network_index

    def model_name_for(self, mode: str) -> str:
        return self.bundle.get("best_model", {}).get(mode, "unknown")

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------
    def predict(
        self,
        route_id: str,
        hour: int,
        on_date: date,
        segment_id: str | None = None,
        weather: str | None = None,
        traffic_level: str | None = None,
        special_event: bool = False,
        origin_id: str | None = None,
        destination_id: str | None = None,
    ) -> dict:
        """Predict the passenger demand of a route segment for one hour.

        ``origin_id`` / ``destination_id`` describe the journey the traveller
        wants to make.  When both are given (and the route serves both places)
        the forecast is made for the busiest stretch of that journey, and the
        reported ride time covers the **whole** journey, not only one stretch.
        """
        index = self.index
        routes = index["routes"]
        if route_id not in routes:
            raise KeyError(route_id)
        route = routes[route_id]
        mode = route["mode"]

        weather = weather or default_weather_for(on_date, hour)
        traffic_level = traffic_level or default_traffic_for(hour, on_date)

        journey = _resolve_journey(index, route_id, origin_id, destination_id)
        resolved_segment_id = journey["segment_id"] if journey else segment_id

        features = build_prediction_features(
            route_id=route_id,
            hour=hour,
            on_date=on_date,
            weather=weather,
            traffic_level=traffic_level,
            special_event=special_event,
            segment_id=resolved_segment_id,
            index=index,
        )
        model = self.bundle["models"][mode]
        prediction = max(0.0, float(model.predict(features)[0]))

        segment = _resolve_segment(index, route_id, resolved_segment_id)
        hourly_capacity = int(features["hourly_capacity"].iloc[0])
        occupancy = prediction / hourly_capacity if hourly_capacity else 0.0
        occupancy = float(min(occupancy, 1.30))

        headway = 60.0 / max(1, int(features["service_frequency"].iloc[0]))
        wait = expected_wait_minutes(mode, headway, occupancy, traffic_level)

        segment_travel = _travel_minutes(
            index, route_id, segment["segment_index"], traffic_level
        )
        if journey and journey["ride_minutes"] is not None:
            travel = journey["ride_minutes"]
        else:
            travel = segment_travel

        result = {
            "route_id": route_id,
            "route_name": route["name"],
            "mode": mode,
            "segment_id": segment["segment_id"],
            "origin_name": segment["origin_name"],
            "dest_name": segment["dest_name"],
            "date": on_date.isoformat(),
            "hour": int(hour),
            "predicted_passengers": int(round(prediction)),
            "predicted_occupancy_pct": round(occupancy * 100.0, 2),
            "crowd_level": crowd_level_for(occupancy),
            "is_overcrowded": bool(occupancy >= 0.80),
            "service_frequency": int(features["service_frequency"].iloc[0]),
            "vehicle_capacity": int(route["vehicle_capacity"]),
            "hourly_capacity": hourly_capacity,
            "waiting_time_min": round(wait, 1),
            "travel_time_min": travel,
            "segment_travel_time_min": segment_travel,
            "total_journey_time_min": round(wait + travel, 1),
            "model_name": self.model_name_for(mode),
            "assumptions": ASSUMPTIONS,
            "data_notice": DATA_NOTICE,
        }
        if journey:
            result["journey"] = journey
        else:
            result["journey"] = None
        return result

    def predict_batch(
        self,
        route_id: str,
        hours: list[int],
        on_date: date,
        segment_id: str | None = None,
        weather: str | None = None,
        traffic_level: str | None = None,
        origin_id: str | None = None,
        destination_id: str | None = None,
    ) -> list[dict]:
        """Predict several hours of the same route (used by the charts)."""
        return [
            self.predict(
                route_id=route_id,
                hour=hour,
                on_date=on_date,
                segment_id=segment_id,
                weather=weather,
                traffic_level=traffic_level,
                origin_id=origin_id,
                destination_id=destination_id,
            )
            for hour in hours
        ]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _index_network(network: dict) -> dict:
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
            "stop_ids": line["stations"],
            "stop_names": line["station_names"],
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
            "stop_ids": route["stops"],
            "stop_names": route["stop_names"],
        }
    segments = {seg["segment_id"]: seg for seg in network["segments"]}
    places = {place["id"]: place for place in network["places"]}
    return {"routes": routes, "segments": segments, "places": places, "network": network}


def _resolve_segment(index: dict, route_id: str, segment_id: str | None) -> dict:
    """Return the requested segment or the busiest segment of the route."""
    segments = index["segments"]
    if segment_id:
        if segment_id not in segments:
            raise KeyError(segment_id)
        if segments[segment_id]["route_id"] != route_id:
            raise ValueError("segment does not belong to route")
        return segments[segment_id]
    candidates = [s for s in segments.values() if s["route_id"] == route_id]
    if not candidates:
        raise KeyError(route_id)
    return max(candidates, key=lambda s: s["segment_index"])


def _resolve_journey(
    index: dict,
    route_id: str,
    origin_id: str | None,
    destination_id: str | None,
) -> dict | None:
    """Turn an (origin, destination) pair into a journey description.

    Returns ``None`` when the pair is incomplete or when the route does not
    serve both places, so the caller can fall back to the route's busiest
    stretch.
    """
    if not origin_id or not destination_id:
        return None
    places = index["places"]
    if origin_id not in places or destination_id not in places:
        return None
    if origin_id == destination_id:
        return None

    segment = segment_between(route_id, origin_id, destination_id)
    if segment is None:
        return None

    traffic_factor = 1.0
    route = index["routes"].get(route_id)
    if route and route["mode"] == "bus":
        traffic_factor = 1.0  # the caller applies the traffic factor

    ride_minutes = journey_ride_minutes(route_id, origin_id, destination_id)
    return {
        "origin_id": origin_id,
        "origin_name": places[origin_id]["name"],
        "destination_id": destination_id,
        "destination_name": places[destination_id]["name"],
        "segment_id": segment["segment_id"],
        "segment_origin_name": segment["origin_name"],
        "segment_dest_name": segment["dest_name"],
        "ride_minutes": ride_minutes,
        "traffic_factor": traffic_factor,
    }


def expected_wait_minutes(
    mode: str, headway_minutes: float, occupancy: float, traffic_level: str
) -> float:
    """Expected wait for the next vehicle, in minutes.

    The formula is deliberately simple and is documented in the README:

    ``wait = headway x MODE_WAIT_PER_HEADWAY[mode]``

    plus two penalties that model what a passenger really experiences:

    * ``+1.2`` min when the service is above 85 % occupancy (boarding is slow and
      a queue forms), and
    * ``+0.8`` min for a bus in heavy or severe traffic (the vehicle is late
      and the queue is longer).

    ``headway`` is ``60 / vehicles_per_hour``.  With 14 vehicles per hour this
    gives 1.9 min for a metro and 2.1 min for a bus.
    """
    wait = float(headway_minutes) * MODE_WAIT_PER_HEADWAY[mode]
    if occupancy > 0.85:
        wait += 1.2
    if traffic_level in ("heavy", "severe") and mode == "bus":
        wait += 0.8
    return round(wait, 1)


def _travel_minutes(
    index: dict, route_id: str, segment_index: int, traffic: str
) -> float:
    """Travel time of a segment, adjusted for the traffic level (buses only)."""
    from navacity_core.config import TRAFFIC_TRAVEL_TIME_FACTOR

    segment = next(
        s
        for s in index["segments"].values()
        if s["route_id"] == route_id and s["segment_index"] == segment_index
    )
    travel = float(segment["travel_minutes"])
    if index["routes"][route_id]["mode"] == "bus":
        travel *= TRAFFIC_TRAVEL_TIME_FACTOR.get(traffic, 1.0)
    return round(travel, 1)


model_service = ModelService()
