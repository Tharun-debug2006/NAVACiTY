"""End-to-end tests of the NavaCity API endpoints."""

from __future__ import annotations


def test_health(client):
    """The health check reports a working database and a loaded model."""
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in ("ok", "degraded")
    assert payload["database"] == "connected"
    assert payload["record_count"] > 0
    assert "SIMULATED" in payload["data_notice"]


def test_root_lists_the_endpoints(client):
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert "/api/predict" in payload["endpoints"]
    assert "SIMULATED" in payload["data_notice"]


def test_openapi_and_docs_are_available(client):
    """The Swagger UI and the OpenAPI schema are served."""
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200


def test_network_contains_metro_and_bus(client):
    payload = client.get("/api/network").json()
    assert payload["city"] == "NavaCity"
    assert len(payload["metro_lines"]) == 6
    assert len(payload["bus_routes"]) == 18
    assert len(payload["places"]) > 40
    # Every place has a usable schematic position.
    for place in payload["places"]:
        assert 0 <= place["x"] <= 100
        assert 0 <= place["y"] <= 100


def test_routes_and_places_filters(client):
    metro = client.get("/api/routes?mode=metro").json()
    bus = client.get("/api/routes?mode=bus").json()
    assert all(route["mode"] == "metro" for route in metro)
    assert all(route["mode"] == "bus" for route in bus)
    assert len(metro) + len(bus) == 24

    stations = client.get("/api/places?kind=station").json()
    stops = client.get("/api/places?kind=stop").json()
    assert all(place["kind"] == "station" for place in stations)
    assert all(place["kind"] == "stop" for place in stops)


def test_invalid_query_parameters_are_rejected(client):
    assert client.get("/api/routes?mode=tram").status_code == 422
    assert client.get("/api/history?limit=0").status_code == 422
    assert client.get("/api/predict?route_id=M1&hour=99").status_code == 422


def test_history_returns_records(client):
    payload = client.get("/api/history?limit=25").json()
    assert payload["count"] == 25
    assert len(payload["records"]) == 25
    first = payload["records"][0]
    assert first["passenger_count"] >= 0
    assert first["crowd_level"] in ("Low", "Moderate", "High", "Critical")


def test_history_hourly_profile_has_24_points(client):
    payload = client.get("/api/history/hourly?route_id=M1").json()
    assert len(payload["points"]) == 24
    assert [point["hour"] for point in payload["points"]] == list(range(24))


def test_crowd_summary(client, authority_headers):
    payload = client.get("/api/crowd-summary?mode=metro", headers=authority_headers).json()
    assert payload["total_records"] > 0
    assert [entry["crowd_level"] for entry in payload["levels"]] == [
        "Low", "Moderate", "High", "Critical"
    ]
    assert 0 <= payload["overcrowded_share_pct"] <= 100
    assert abs(sum(entry["share_pct"] for entry in payload["levels"]) - 100) < 1.0


def test_alerts_only_return_crowded_segments(client, authority_headers):
    payload = client.get("/api/alerts?limit=10", headers=authority_headers).json()
    assert payload["threshold_pct"] == 80.0
    assert payload["count"] <= 10
    for alert in payload["alerts"]:
        assert alert["mean_occupancy_pct"] >= 80.0
        assert alert["severity"] in ("warning", "critical")


def test_authority_stats(client, authority_headers):
    payload = client.get("/api/authority/stats", headers=authority_headers).json()
    assert payload["total_routes"] == 24
    assert payload["total_records"] > 10000
    assert payload["total_passengers"] > 0
    assert len(payload["kpis"]) == 6
    assert len(payload["mode_comparison"]) == 2
    assert len(payload["route_analytics"]) == 24
    assert len(payload["hourly_analytics"]) == 24
    assert len(payload["peak_hours"]) == 3
    assert "SIMULATED" in payload["data_notice"]


def test_recommendations_are_labelled_as_recommendations(client, authority_headers):
    payload = client.get(
        "/api/authority/recommendations?limit=5", headers=authority_headers
    ).json()
    assert "recommendation" in payload["disclaimer"].lower()
    for item in payload["recommendations"]:
        assert item["recommended_frequency"] >= 1
        assert item["change"] != 0
        assert item["confidence"] in ("low", "medium", "high")


def test_model_metrics_are_exposed(client, authority_headers):
    payload = client.get("/api/model/metrics", headers=authority_headers).json()
    assert "metro" in payload["modes"]
    assert "bus" in payload["modes"]
    for mode in ("metro", "bus"):
        metrics = payload["modes"][mode]["time_ordered_metrics"]
        assert metrics["mae"] > 0
        assert metrics["rmse"] >= metrics["mae"]
        assert -1.0 <= metrics["r2"] <= 1.0
