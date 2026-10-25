"""Consistency tests of the shared NavaCity network.

The route definitions live in exactly one place
(:mod:`navacity_core.network`) and are consumed by the simulator, the
generated dataset, the trained model, the database, the API and the SVG map.
These tests make sure that the expansion of the bus network stayed
consistent everywhere.

They also pin the *existing* route ids and their behaviour, so that a
future change cannot silently drop or renumber a route.
"""

from __future__ import annotations

import json

import pytest

from navacity_core.config import RANDOM_SEED
from navacity_core.events import SPECIAL_EVENTS
from navacity_core.features import FEATURE_COLUMNS, build_prediction_features
from navacity_core.network import (
    BUS_ROUTES,
    METRO_LINES,
    ROUTE_POPULARITY,
    ROUTE_TRAVEL_MINUTES,
    VEHICLE_CAPACITY,
    build_network,
)

#: The metro lines must keep their ids and their station order.
EXPECTED_METRO = {
    "M1": [
        "NavaCity Central", "Mahatma Nagar", "City Park", "Saraswati Junction",
        "Tech Park Gate", "Aerodrome Interchange", "Whitefield Depot",
    ],
    "M2": [
        "Riverfront", "Gandhi Chowk", "Lalbagh", "Vidhana Soudha",
        "NavaCity Central", "Market Yard", "Old Town Gate", "Hill View",
    ],
    "M3": [
        "Hebbal Farm", "Yelahanka New Town", "Kogilu Cross",
        "Indira Nagar 2nd Stage", "Domlur Flyover", "Laxmi Road",
        "NavaCity Central", "Chinnaswamy Park",
    ],
    "M4": [
        "Peenya Industrial Area", "Jnanabharathi Circle", "Yeshwanthpur",
        "Majestic", "KR Market", "NavaCity Central", "Hosahalli", "Silk Board",
    ],
    "M5": [
        "Bannerghatta Road", "HSR Layout Sector 2", "BTM Layout",
        "Jayanagar 4th Block", "South End", "NavaCity Central", "Banashankari",
        "Padmanabha Nagar",
    ],
    "M6": [
        "Devanahalli", "Kempegowda Intl Airport", "Hebbal Flyover",
        "Bellandur Lake", "Kadugodi Tree Park", "Marathahalli Bridge",
        "Silk Board", "NavaCity Central",
    ],
}

#: The bus routes that existed before the expansion.  Their ids, names and
#: stop order must not change.
EXPECTED_BUS_LEGACY = {
    "B01": [
        "Kempegowda Intl Airport", "Hebbal Flyover", "Bellandur Lake",
        "Marathahalli Bridge", "Domlur Flyover", "Laxmi Road",
        "Vidhana Soudha", "Majestic",
    ],
    "B02": [
        "Old Town Gate", "Hill View", "Gandhi Chowk", "Riverfront",
        "Market Yard", "Gandhi Chowk", "Old Town Gate",
    ],
    "B03": [
        "Whitefield Depot", "Brookefield Gate", "Kundalahalli Gate",
        "Brookefield Circle", "ITPL Tech Park", "Tech Park Gate",
        "Saraswati Junction", "City Park",
    ],
    "B04": [
        "Devanahalli", "Kempegowda Intl Airport", "Bellandur Lake",
        "Kadugodi Tree Park", "Marathahalli Bridge",
    ],
    "B05": [
        "Bannerghatta Road", "HSR Layout Sector 2", "BTM Layout",
        "Jayanagar 4th Block", "South End", "Banashankari", "Padmanabha Nagar",
    ],
    "B06": [
        "Hebbal Farm", "Yelahanka New Town", "Kogilu Cross",
        "Indira Nagar 2nd Stage", "Domlur Flyover", "Laxmi Road",
    ],
    "B07": [
        "KR Market", "NavaCity Central Bus Depot", "Vidhana Soudha",
        "Lalbagh", "Jayanagar 4th Block", "KR Market",
    ],
    "B08": [
        "Peenya Industrial Area", "Jnanabharathi Circle", "Yeshwanthpur",
        "Majestic", "NavaCity Central Bus Depot",
    ],
    "B09": [
        "Kadugodi Tree Park", "Bellandur Lake", "Marathahalli Bridge",
        "Silk Board", "Jayanagar 4th Block", "Banashankari",
    ],
    "B10": [
        "Jnanabharathi Circle", "Yeshwanthpur", "KR Market",
        "NavaCity Central Bus Depot", "Vidhana Soudha", "Jnanabharathi Circle",
    ],
}

#: The routes that were added by the expansion.
EXPECTED_BUS_NEW = [
    "B11", "B12", "B13", "B14", "B15", "B16", "B17", "B18",
]



# --------------------------------------------------------------------------
# The shape of the network
# --------------------------------------------------------------------------
def test_the_network_has_six_metro_lines():
    assert len(METRO_LINES) == 6
    assert [line["id"] for line in METRO_LINES] == ["M1", "M2", "M3", "M4", "M5", "M6"]


def test_the_network_has_eighteen_bus_routes():
    assert len(BUS_ROUTES) == 18
    ids = [route["id"] for route in BUS_ROUTES]
    assert ids[:10] == [f"B{n:02d}" for n in range(1, 11)]
    assert ids[10:] == EXPECTED_BUS_NEW


def test_the_existing_metro_lines_are_unchanged():
    for line in METRO_LINES:
        assert line["stations"] == EXPECTED_METRO[line["id"]]


def test_the_existing_bus_routes_are_unchanged():
    stops = {route["id"]: route["stops"] for route in BUS_ROUTES}
    for route_id, expected in EXPECTED_BUS_LEGACY.items():
        assert stops[route_id] == expected


def test_every_route_has_a_name_and_a_base_frequency():
    for route in BUS_ROUTES:
        assert route["name"]
        assert route["base_frequency"] >= 1
    for line in METRO_LINES:
        assert line["name"]
        assert line["color"].startswith("#")


def test_every_route_has_a_popularity_weight_and_a_travel_time():
    route_ids = [line["id"] for line in METRO_LINES] + [
        route["id"] for route in BUS_ROUTES
    ]
    for route_id in route_ids:
        assert route_id in ROUTE_POPULARITY
        assert route_id in ROUTE_TRAVEL_MINUTES
        assert ROUTE_POPULARITY[route_id] > 0
        assert ROUTE_TRAVEL_MINUTES[route_id] > 0


def test_the_new_bus_routes_are_connected_to_the_network():
    """Every new route must serve at least three known places."""
    network = build_network()
    known = {place["name"] for place in network["places"]}
    for route in BUS_ROUTES:
        if route["id"] not in EXPECTED_BUS_NEW:
            continue
        assert len(route["stops"]) >= 3
        for stop in route["stops"]:
            assert stop in known, f"{route['id']} serves the unknown stop {stop}"


def test_the_new_bus_routes_serve_an_interchange():
    """A new route must connect to the rest of the network."""
    network = build_network()
    interchanges = {
        place["name"] for place in network["places"] if place["is_interchange"]
    }
    for route in BUS_ROUTES:
        if route["id"] not in EXPECTED_BUS_NEW:
            continue
        assert interchanges & set(route["stops"]), (
            f"{route['id']} does not share a single interchange with the network"
        )



# --------------------------------------------------------------------------
# The built network
# --------------------------------------------------------------------------
def test_the_built_network_is_consistent():
    network = build_network()
    assert len(network["metro_lines"]) == 6
    assert len(network["bus_routes"]) == 18
    assert network["city"] == "NavaCity"
    assert "SIMULATED" in network["data_notice"]


def test_every_segment_points_at_known_places():
    network = build_network()
    place_ids = {place["id"] for place in network["places"]}
    assert network["segments"]
    for segment in network["segments"]:
        assert segment["origin_id"] in place_ids
        assert segment["dest_id"] in place_ids
        assert segment["num_stops"] >= 2
        assert segment["travel_minutes"] > 0


def test_the_segment_ids_are_unique():
    network = build_network()
    ids = [segment["segment_id"] for segment in network["segments"]]
    assert len(ids) == len(set(ids))


def test_every_place_has_a_position_on_the_schematic_grid():
    network = build_network()
    for place in network["places"]:
        assert 0 <= place["x"] <= 100
        assert 0 <= place["y"] <= 100
        assert place["kind"] in ("station", "stop")


def test_the_place_ids_are_unique():
    network = build_network()
    ids = [place["id"] for place in network["places"]]
    assert len(ids) == len(set(ids))


def test_the_network_json_matches_the_shared_definition():
    """The generated JSON must describe the same network as the module."""
    from navacity_core.config import NETWORK_JSON

    if not NETWORK_JSON.exists():  # pragma: no cover
        pytest.skip("The network JSON has not been generated yet.")

    payload = json.loads(NETWORK_JSON.read_text(encoding="utf-8"))
    network = build_network()

    assert [line["id"] for line in payload["metro_lines"]] == [
        line["id"] for line in network["metro_lines"]
    ]
    assert [route["id"] for route in payload["bus_routes"]] == [
        route["id"] for route in network["bus_routes"]
    ]
    assert len(payload["places"]) == len(network["places"])
    assert len(payload["segments"]) == len(network["segments"])


# --------------------------------------------------------------------------
# The model input space


# --------------------------------------------------------------------------
# The generated dataset
# --------------------------------------------------------------------------
def test_the_dataset_covers_every_route(client):
    """The seeded dataset must contain observations for all 24 routes."""
    from sqlalchemy import select

    from backend.app.database import DemandRecord, SessionLocal

    session = SessionLocal()
    try:
        route_ids = {
            row[0]
            for row in session.execute(
                select(DemandRecord.route_id).distinct()
            ).all()
        }
    finally:
        session.close()

    expected = {line["id"] for line in METRO_LINES} | {
        route["id"] for route in BUS_ROUTES
    }
    assert route_ids == expected


def test_the_dataset_covers_every_new_bus_route(client):
    from sqlalchemy import func, select

    from backend.app.database import DemandRecord, SessionLocal

    session = SessionLocal()
    try:
        counts = dict(
            session.execute(
                select(DemandRecord.route_id, func.count(DemandRecord.id)).group_by(
                    DemandRecord.route_id
                )
            ).all()
        )
    finally:
        session.close()

    for route_id in EXPECTED_BUS_NEW:
        assert counts.get(route_id, 0) > 0, f"{route_id} has no records"


# --------------------------------------------------------------------------
# The special events
# --------------------------------------------------------------------------
def test_the_special_events_only_reference_known_routes_and_places():
    network = build_network()
    route_ids = {line["id"] for line in network["metro_lines"]} | {
        route["id"] for route in network["bus_routes"]
    }
    place_names = {place["name"] for place in network["places"]}

    for event in SPECIAL_EVENTS:
        for route_id in event["routes"]:
            assert route_id in route_ids, f"{event['id']} references {route_id}"
        for place in event["places"]:
            assert place in place_names, f"{event['id']} references {place}"


def test_the_simulation_seed_is_unchanged():
    """The dataset generation must stay deterministic."""
    assert RANDOM_SEED == 20250615


def test_the_vehicle_capacity_is_unchanged():
    assert VEHICLE_CAPACITY == {"metro": 320, "bus": 48}

# --------------------------------------------------------------------------
@pytest.mark.parametrize("route_id", ["M1", "M6", "B01", "B10", "B11", "B18"])
def test_every_route_can_be_predicted(route_id):
    """The model must accept every route of the (expanded) network."""
    from datetime import date

    features = build_prediction_features(
        route_id=route_id, hour=8, on_date=date(2025, 6, 30)
    )
    assert list(features.columns) == FEATURE_COLUMNS
    assert int(features["hour"].iloc[0]) == 8
    assert int(features["service_frequency"].iloc[0]) > 0
    assert features["route_popularity"].iloc[0] > 0
