"""Alternative route suggestions for the public dashboard.

The suggestions are derived from the simulated network: a candidate has to
serve the requested origin and destination (directly, or with one transfer at
a shared interchange).  Every candidate is then scored with the *same* model
that serves the main prediction, so the comparison is apples to apples.
"""

from __future__ import annotations

from datetime import date

from navacity_core.config import CROWD_LEVELS

from ..schemas import AlternativesResponse, AlternativeRoute
from .model_service import model_service

DATA_NOTICE = (
    "SIMULATED DATA - NavaCity is a fictional city. All figures are produced "
    "by a rule-based simulator and a model trained on that simulated data."
)

# Ordering of the crowd levels from the best to the worst.
_CROWD_RANK = {level: index for index, level in enumerate(CROWD_LEVELS)}

# Extra minutes added to the total journey time of a one-transfer journey.
# Changing vehicles costs the passenger time (walking across the interchange
# and waiting for the next service).
TRANSFER_PENALTY_MIN = 4.0


def _stop_index() -> dict[str, list[str]]:
    """Map every place id to the routes that serve it."""
    index = model_service.index
    table: dict[str, list[str]] = {}
    for route_id, route in index["routes"].items():
        for stop_id in route["stop_ids"]:
            table.setdefault(stop_id, []).append(route_id)
    return table


def suggest_alternatives(
    route_id: str,
    origin_id: str,
    destination_id: str,
    hour: int,
    on_date: date,
    max_results: int = 5,
) -> AlternativesResponse:
    """Return the less crowded alternatives of the requested route."""
    index = model_service.index
    routes = index["routes"]
    places = index["places"]

    if route_id not in routes:
        raise KeyError(route_id)

    origin_name = places.get(origin_id, {}).get("name", origin_id)
    destination_name = places.get(destination_id, {}).get("name", destination_id)

    serving = _stop_index()
    origin_routes = set(serving.get(origin_id, []))
    destination_routes = set(serving.get(destination_id, []))

    direct = origin_routes & destination_routes
    # One transfer: the two routes share at least one interchange place.
    transfer_pairs: list[tuple[str, str]] = []
    for o_route in origin_routes:
        for d_route in destination_routes:
            if o_route == d_route or o_route == route_id or d_route == route_id:
                continue
            shared = set(routes[o_route]["stop_ids"]) & set(routes[d_route]["stop_ids"])
            if shared:
                transfer_pairs.append((o_route, d_route))

    # The journey time of the route the traveller asked about.  It is the
    # reference every alternative is compared against.
    requested = model_service.predict(
        route_id, hour, on_date, origin_id=origin_id, destination_id=destination_id
    )
    requested_total = requested.get("total_journey_time_min")

    candidates: list[AlternativeRoute] = []

    for candidate in sorted(direct):
        if candidate == route_id:
            continue
        prediction = model_service.predict(
            candidate, hour, on_date, origin_id=origin_id, destination_id=destination_id
        )
        candidates.append(
            _to_alternative(
                prediction, direct=True, transfers=0,
                reason="Serves the same origin and destination without a transfer.",
            )
        )

    for o_route, d_route in sorted(transfer_pairs):
        # The first leg carries the traveller to the interchange, the second
        # leg carries them to the destination.  Both legs add to the total
        # journey time, and a transfer costs extra waiting time.
        change_at = _shared_place(o_route, d_route, origin_id, destination_id)
        if change_at is None:
            continue
        first = model_service.predict(
            o_route, hour, on_date, origin_id=origin_id, destination_id=change_at
        )
        second = model_service.predict(
            d_route, hour, on_date, origin_id=change_at, destination_id=destination_id
        )
        combined = _combine_transfer(first, second, TRANSFER_PENALTY_MIN)
        candidates.append(
            _to_alternative(
                combined,
                direct=False,
                transfers=1,
                reason=(
                    f"Continue on {routes[o_route]['name']} and change to "
                    f"{routes[d_route]['name']} at a shared interchange."
                ),
            )
        )

    # Rank: same mode first, then the total journey time, then the crowd
    # level.  The comparison is against the route the traveller already chose.
    requested_mode = routes[route_id]["mode"]
    candidates.sort(
        key=lambda item: (
            0 if item.mode == requested_mode else 1,
            item.total_journey_time_min,
            _CROWD_RANK.get(item.crowd_level, 99),
            item.predicted_occupancy_pct,
        )
    )

    return AlternativesResponse(
        origin=origin_name,
        destination=destination_name,
        requested_route=route_id,
        hour=int(hour),
        date=on_date.isoformat(),
        data_notice=DATA_NOTICE,
        requested_total_journey_time_min=requested_total,
        requested_crowd_level=requested["crowd_level"],
        alternatives=candidates[:max_results],
    )


def _shared_place(
    route_a: str, route_b: str, origin_id: str, destination_id: str
) -> str | None:
    """The interchange where a one-transfer journey changes vehicles."""
    index = model_service.index
    stops_a = set(index["routes"][route_a]["stop_ids"])
    stops_b = set(index["routes"][route_b]["stop_ids"])
    shared = stops_a & stops_b
    if not shared:
        return None
    # Prefer an interchange that is not the origin or the destination itself.
    for place_id in sorted(shared):
        if place_id not in (origin_id, destination_id):
            return place_id
    return sorted(shared)[0]


def _combine_transfer(first: dict, second: dict, penalty: float) -> dict:
    """Merge the two legs of a one-transfer journey into one prediction."""
    wait = float(first["waiting_time_min"]) + float(second["waiting_time_min"]) + penalty
    ride = float(first["travel_time_min"]) + float(second["travel_time_min"])
    combined = dict(second)
    combined["waiting_time_min"] = round(wait, 1)
    combined["travel_time_min"] = round(ride, 1)
    combined["total_journey_time_min"] = round(wait + ride, 1)
    combined["origin_name"] = first["origin_name"]
    combined["dest_name"] = second["dest_name"]
    return combined


def _to_alternative(
    prediction: dict, direct: bool, transfers: int, reason: str
) -> AlternativeRoute:
    total = prediction.get("total_journey_time_min")
    if total is None:
        total = round(
            float(prediction["waiting_time_min"]) + float(prediction["travel_time_min"]), 1
        )
    return AlternativeRoute(
        route_id=prediction["route_id"],
        route_name=prediction["route_name"],
        mode=prediction["mode"],
        segment_id=prediction["segment_id"],
        origin_name=prediction["origin_name"],
        dest_name=prediction["dest_name"],
        predicted_passengers=prediction["predicted_passengers"],
        predicted_occupancy_pct=prediction["predicted_occupancy_pct"],
        crowd_level=prediction["crowd_level"],
        waiting_time_min=prediction["waiting_time_min"],
        travel_time_min=prediction["travel_time_min"],
        total_journey_time_min=total,
        service_frequency=prediction["service_frequency"],
        direct=direct,
        transfers=transfers,
        reason=reason,
    )
