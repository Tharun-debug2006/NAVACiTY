"""Tests of the journey-aware forecast, the date range and the alternatives.

These tests cover the behaviour that the review found missing:

* the origin and the destination really determine the forecast (C1),
* a date outside the simulated window is reported as an extrapolation (C2),
* the alternatives are ranked and compared by the *total* journey time (I2),
* the waiting-time formula is the documented one (I7),
* the bus stop count is the number of places a bus can stop at (I3),
* the authority endpoints can be filtered by transport mode (Phase 5).
"""

from __future__ import annotations

from datetime import date

import pytest

from backend.app.services.model_service import (
    expected_wait_minutes,
    model_service,
)
from navacity_core.config import (
    OBSERVED_MONTHS,
    SIM_END_DATE,
    SIM_START_DATE,
    is_within_observed_months,
    is_within_simulated_window,
)
from navacity_core.network import (
    MODE_WAIT_PER_HEADWAY,
    journey_ride_minutes,
    route_path_segments,
    segment_between,
)

ON_DATE = date(2025, 6, 30)


# --------------------------------------------------------------------------
# C1 - the origin and the destination determine the segment
# --------------------------------------------------------------------------
def test_segment_between_finds_the_stretch_of_the_journey():
    """A short journey must not resolve to the busiest stretch of the route."""
    network = model_service.network
    line = next(l for l in network["metro_lines"] if l["id"] == "M1")
    first_id, second_id = line["stations"][0], line["stations"][1]

    segment = segment_between("M1", first_id, second_id)
    assert segment is not None
    assert segment["origin_id"] == first_id
    assert segment["dest_id"] == second_id

    # The busiest stretch of M1 is a different one.
    busiest = max(
        (s for s in network["segments"] if s["route_id"] == "M1"),
        key=lambda s: s["segment_index"],
    )
    assert segment["segment_id"] != busiest["segment_id"]


def test_the_prediction_changes_with_the_journey(client):
    """Two different journeys on the same line give different forecasts."""
    network = model_service.network
    line = next(l for l in network["metro_lines"] if l["id"] == "M1")
    stations = line["stations"]

    near = model_service.predict(
        "M1", 8, ON_DATE,
        origin_id=stations[0], destination_id=stations[1],
    )
    far = model_service.predict(
        "M1", 8, ON_DATE,
        origin_id=stations[0], destination_id=stations[-1],
    )

    assert near["segment_id"] != far["segment_id"]
    assert near["journey"]["destination_id"] != far["journey"]["destination_id"]


def test_the_journey_ride_time_covers_the_whole_journey(client):
    """The ride time is the sum of the stretches, not of a single stretch."""
    network = model_service.network
    line = next(l for l in network["metro_lines"] if l["id"] == "M1")
    stations = line["stations"]

    short = model_service.predict(
        "M1", 8, ON_DATE,
        origin_id=stations[0], destination_id=stations[1],
    )
    long = model_service.predict(
        "M1", 8, ON_DATE,
        origin_id=stations[0], destination_id=stations[-1],
    )

    assert long["travel_time_min"] > short["travel_time_min"]
    assert long["total_journey_time_min"] == pytest.approx(
        long["waiting_time_min"] + long["travel_time_min"], abs=0.15
    )
    # The single-stretch time is reported separately and is not longer.
    assert long["segment_travel_time_min"] <= long["travel_time_min"]


def test_the_api_accepts_the_origin_and_the_destination(client):
    """POST /api/predict must honour the journey of the traveller."""
    network = model_service.network
    line = next(l for l in network["metro_lines"] if l["id"] == "M1")
    stations = line["stations"]

    response = client.post(
        "/api/predict",
        json={
            "route_id": "M1",
            "hour": 8,
            "date": ON_DATE.isoformat(),
            "origin_id": stations[0],
            "destination_id": stations[1],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["journey"]["origin_id"] == stations[0]
    assert payload["journey"]["destination_id"] == stations[1]
    assert payload["journey"]["segment_id"]


def test_the_day_prediction_accepts_the_origin_and_the_destination(client):
    network = model_service.network
    line = next(l for l in network["metro_lines"] if l["id"] == "M1")
    stations = line["stations"]
    response = client.get(
        "/api/predict/day",
        params={
            "route_id": "M1",
            "date": ON_DATE.isoformat(),
            "origin_id": stations[0],
            "destination_id": stations[1],
        },
    )
    assert response.status_code == 200
    assert len(response.json()["predictions"]) == 24


def test_the_route_path_covers_every_stretch(client):
    network = model_service.network
    line = next(l for l in network["metro_lines"] if l["id"] == "M1")
    stations = line["stations"]
    path = route_path_segments("M1", stations[0], stations[-1])
    assert len(path) == len(stations) - 1
    # The ride time of the path is the sum of the stretches.
    total = journey_ride_minutes("M1", stations[0], stations[-1])
    assert total == pytest.approx(sum(s["travel_minutes"] for s in path), abs=0.2)


# --------------------------------------------------------------------------
# C2 / I10 - the date range
# --------------------------------------------------------------------------
def test_a_date_outside_the_window_is_an_extrapolation(client):
    response = client.post(
        "/api/predict",
        json={"route_id": "M1", "hour": 8, "date": "2026-10-22"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["is_extrapolation"] is True
    assert payload["extrapolation_notice"]
    assert payload["supported_date_range"]["start"] == SIM_START_DATE.isoformat()
    assert payload["supported_date_range"]["end"] == SIM_END_DATE.isoformat()


def test_a_date_inside_the_window_is_not_an_extrapolation(client):
    response = client.post(
        "/api/predict",
        json={"route_id": "M1", "hour": 8, "date": ON_DATE.isoformat()},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["is_extrapolation"] is False
    assert payload["extrapolation_notice"] is None


def test_the_observed_months_are_the_simulated_ones():
    assert OBSERVED_MONTHS == frozenset({1, 2, 3, 4, 5, 6})
    assert is_within_observed_months(date(2025, 3, 15)) is True
    assert is_within_observed_months(date(2025, 9, 15)) is False
    assert is_within_simulated_window(date(2025, 9, 15)) is False
    assert is_within_simulated_window(date(2025, 3, 15)) is True


def test_the_day_endpoint_reports_the_extrapolation(client):
    response = client.get(
        "/api/predict/day", params={"route_id": "M1", "date": "2026-10-22"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["is_extrapolation"] is True
    assert payload["supported_date_range"]["observed_months"] == [1, 2, 3, 4, 5, 6]


# --------------------------------------------------------------------------
# I2 - the alternatives are compared by the total journey time
# --------------------------------------------------------------------------
def test_the_alternatives_carry_a_total_journey_time(client):
    network = model_service.network
    line = next(l for l in network["metro_lines"] if l["id"] == "M1")
    stations = line["stations"]

    response = client.get(
        "/api/alternatives",
        params={
            "route_id": "M1",
            "origin_id": stations[0],
            "destination_id": stations[-1],
            "hour": 8,
            "date": ON_DATE.isoformat(),
        },
    )
    assert response.status_code == 200
    payload = response.json()

    # The response states the journey time of the route that was asked about.
    assert payload["requested_total_journey_time_min"] is not None
    assert payload["requested_crowd_level"]

    for item in payload["alternatives"]:
        assert item["total_journey_time_min"] == pytest.approx(
            item["waiting_time_min"] + item["travel_time_min"], abs=0.15
        )


def test_the_alternatives_are_ordered_by_the_total_journey_time(client):
    """The list is ordered: same mode first, then by the total journey time."""
    network = model_service.network
    line = next(l for l in network["metro_lines"] if l["id"] == "M1")
    stations = line["stations"]

    response = client.get(
        "/api/alternatives",
        params={
            "route_id": "M1",
            "origin_id": stations[0],
            "destination_id": stations[-1],
            "hour": 8,
            "date": ON_DATE.isoformat(),
            "limit": 10,
        },
    )
    assert response.status_code == 200
    items = response.json()["alternatives"]
    if len(items) < 2:
        pytest.skip("this journey has fewer than two alternatives")

    modes = [item["mode"] for item in items]
    # Every same-mode option comes before the first cross-mode option.
    if "bus" in modes and "metro" in modes:
        assert modes.index("bus") > max(
            index for index, m in enumerate(modes) if m == "metro"
        )

    # Inside a mode group the list is ordered by the total journey time.
    for mode in ("metro", "bus"):
        times = [
            item["total_journey_time_min"] for item in items if item["mode"] == mode
        ]
        assert times == sorted(times)


def test_the_alternatives_title_matches_the_query(client):
    """The title of the panel describes the journey that was executed."""
    network = model_service.network
    line = next(l for l in network["metro_lines"] if l["id"] == "M1")
    stations = line["stations"]
    places = {p["id"]: p["name"] for p in network["places"]}

    response = client.get(
        "/api/alternatives",
        params={
            "route_id": "M1",
            "origin_id": stations[0],
            "destination_id": stations[-1],
            "hour": 8,
            "date": ON_DATE.isoformat(),
        },
    )
    payload = response.json()
    assert payload["origin"] == places[stations[0]]
    assert payload["destination"] == places[stations[-1]]


# --------------------------------------------------------------------------
# I7 - the waiting-time formula
# --------------------------------------------------------------------------
def test_the_waiting_time_formula():
    """wait = headway x MODE_WAIT_PER_HEADWAY[mode] (+ the two penalties)."""
    # 14 vehicles per hour -> a headway of 60 / 14 = 4.2857 minutes.
    headway = 60.0 / 14
    assert expected_wait_minutes("metro", headway, 0.5, "light") == pytest.approx(
        1.9, abs=0.05
    )
    assert expected_wait_minutes("bus", headway, 0.5, "light") == pytest.approx(
        2.1, abs=0.05
    )
    # The formula is exactly the documented one.
    for mode, factor in MODE_WAIT_PER_HEADWAY.items():
        assert expected_wait_minutes(mode, headway, 0.5, "light") == round(
            headway * factor, 1
        )


def test_the_waiting_time_penalties():
    headway = 60.0 / 14
    # Above 85 % occupancy a queue forms: +1.2 minutes.
    assert expected_wait_minutes("metro", headway, 0.90, "light") == pytest.approx(
        round(headway * 0.45, 1) + 1.2, abs=0.05
    )
    # Heavy traffic on a bus: +0.8 minutes.
    assert expected_wait_minutes("bus", headway, 0.5, "heavy") == pytest.approx(
        round(headway * 0.50, 1) + 0.8, abs=0.05
    )
    # A metro in heavy traffic is not penalised.
    assert expected_wait_minutes("metro", headway, 0.5, "severe") == pytest.approx(
        round(headway * 0.45, 1), abs=0.05
    )


def test_the_prediction_uses_the_documented_waiting_time(client):
    result = model_service.predict("M1", 8, ON_DATE)
    headway = 60.0 / result["service_frequency"]
    expected = expected_wait_minutes(
        "metro", headway, result["predicted_occupancy_pct"] / 100.0, "light"
    )
    # The traffic level of the hour may add the bus penalty, but for a metro
    # the value is the formula.
    assert result["waiting_time_min"] == pytest.approx(expected, abs=0.05)


# --------------------------------------------------------------------------
# I3 - the stop count
# --------------------------------------------------------------------------
def test_the_bus_stop_count_is_the_number_of_served_places(client, authority_headers):
    """The dashboard must report the places a bus can stop at."""
    response = client.get("/api/authority/stats", headers=authority_headers)
    assert response.status_code == 200
    payload = response.json()

    # Every place that is served by a bus route is a place a bus stops at.
    places = client.get("/api/places?kind=station").json()
    stops = client.get("/api/places?kind=stop").json()
    served_by_a_bus = [
        place for place in places + stops if place["bus_routes"]
    ]
    assert payload["total_stops"] == len(served_by_a_bus)
    assert payload["total_stops"] > 5  # the old, wrong "bus-only stops" count
    assert payload["total_stations"] == len(places)


# --------------------------------------------------------------------------
# The authority endpoints can be filtered by transport mode
# --------------------------------------------------------------------------
def test_the_authority_stats_can_be_filtered_by_mode(client, authority_headers):
    everything = client.get("/api/authority/stats", headers=authority_headers).json()
    metro = client.get(
        "/api/authority/stats", params={"mode": "metro"}, headers=authority_headers
    ).json()
    bus = client.get(
        "/api/authority/stats", params={"mode": "bus"}, headers=authority_headers
    ).json()

    assert metro["mode"] == "metro"
    assert bus["mode"] == "bus"
    assert all(item["mode"] == "metro" for item in metro["route_analytics"])
    assert all(item["mode"] == "bus" for item in bus["route_analytics"])
    assert metro["total_records"] + bus["total_records"] == everything["total_records"]
    assert len(metro["route_analytics"]) == 6
    assert len(bus["route_analytics"]) == 18


def test_the_alerts_can_be_filtered_by_mode(client, authority_headers):
    metro = client.get(
        "/api/alerts", params={"mode": "metro", "limit": 50}, headers=authority_headers
    ).json()
    bus = client.get(
        "/api/alerts", params={"mode": "bus", "limit": 50}, headers=authority_headers
    ).json()
    assert all(alert["mode"] == "metro" for alert in metro["alerts"])
    assert all(alert["mode"] == "bus" for alert in bus["alerts"])


def test_the_recommendations_can_be_filtered_by_mode(client, authority_headers):
    response = client.get(
        "/api/authority/recommendations",
        params={"mode": "bus", "limit": 20},
        headers=authority_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "bus"
    assert all(item["mode"] == "bus" for item in payload["recommendations"])
    # Every recommendation states the rule that produced it.
    for item in payload["recommendations"]:
        assert item["rule"]
        assert item["disclaimer"]


def test_the_mode_summary_uses_comparable_metrics(client, authority_headers):
    response = client.get("/api/authority/mode-summary", headers=authority_headers)
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["comparison"]) == 2
    for item in payload["comparison"]:
        assert item["passengers_per_vehicle"] > 0
        assert item["overcrowded_share_pct"] >= 0
    assert payload["busiest_route"]["metro"]
    assert payload["busiest_route"]["bus"]


def test_the_overcrowded_share_is_a_real_count(client, authority_headers):
    """The share of the overcrowded observations must not collapse to zero.

    ``func.sum()`` on a Boolean column returns the boolean ``True`` on SQLite
    instead of a count, which silently turned every overcrowded share into
    zero.  The regression test pins the number down.
    """
    response = client.get("/api/authority/stats", headers=authority_headers)
    payload = response.json()
    for item in payload["mode_comparison"]:
        assert item["overcrowded_records"] > 0
        assert item["overcrowded_share_pct"] > 0
        # The share is consistent with the two numbers it is built from.
        assert item["overcrowded_share_pct"] == pytest.approx(
            100.0 * item["overcrowded_records"] / item["records"], abs=0.05
        )


def test_the_hourly_overcrowded_share_is_a_real_count(client, authority_headers):
    """The peak-hours table must show a real overcrowded share."""
    response = client.get("/api/authority/stats", headers=authority_headers)
    payload = response.json()
    peaks = sorted(
        payload["hourly_analytics"], key=lambda h: h["mean_occupancy_pct"], reverse=True
    )[:5]
    assert peaks
    for hour in peaks:
        assert hour["overcrowded_share_pct"] > 0
        assert hour["observations"] > 0
