"""Tests of the prediction pipeline (model service and the predict endpoint)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.app.services.model_service import model_service
from navacity_core.config import (
    CROWD_HIGH_MAX,
    CROWD_LOW_MAX,
    CROWD_MODERATE_MAX,
    crowd_level_for,
)
from navacity_core.features import (
    FEATURE_COLUMNS,
    LEAKY_COLUMNS,
    build_prediction_features,
    prepare_training_frame,
)


# --------------------------------------------------------------------------
# Feature engineering
# --------------------------------------------------------------------------
def test_feature_matrix_has_no_leaky_columns():
    """The target and its derivatives must never be model inputs."""
    assert not set(FEATURE_COLUMNS) & set(LEAKY_COLUMNS)
    assert "passenger_count" not in FEATURE_COLUMNS
    assert "occupancy_pct" not in FEATURE_COLUMNS
    assert "crowd_level" not in FEATURE_COLUMNS


def test_prepare_training_frame_drops_leaky_columns(client):
    import pandas as pd

    from backend.app.config import settings

    df = pd.read_csv(settings.dataset_csv).head(50)
    frame = prepare_training_frame(df)
    assert list(frame.columns) == FEATURE_COLUMNS
    for leaky in LEAKY_COLUMNS:
        assert leaky not in frame.columns
    assert frame.notna().all().all()


def test_prediction_features_match_the_training_format():
    features = build_prediction_features(
        route_id="M1", hour=8, on_date=date(2025, 6, 30)
    )
    assert list(features.columns) == FEATURE_COLUMNS
    assert len(features) == 1
    assert int(features["hour"].iloc[0]) == 8
    assert features["service_frequency"].iloc[0] > 0


def test_prediction_features_reject_an_unknown_route():
    with pytest.raises(KeyError):
        build_prediction_features(
            route_id="ZZ9", hour=8, on_date=date(2025, 6, 30)
        )


def test_prediction_features_reject_a_foreign_segment():
    with pytest.raises(ValueError):
        build_prediction_features(
            route_id="M1", hour=8, on_date=date(2025, 6, 30), segment_id="B01-S01"
        )


# --------------------------------------------------------------------------
# Crowd level rules
# --------------------------------------------------------------------------
def test_crowd_level_thresholds():
    assert crowd_level_for(0.10) == "Low"
    assert crowd_level_for(CROWD_LOW_MAX) == "Moderate"
    assert crowd_level_for(CROWD_MODERATE_MAX) == "High"
    assert crowd_level_for(CROWD_HIGH_MAX) == "Critical"
    assert crowd_level_for(1.20) == "Critical"


# --------------------------------------------------------------------------
# The model service
# --------------------------------------------------------------------------
def test_model_service_is_loaded(client):
    assert model_service.is_loaded
    assert set(model_service.bundle["models"]) == {"metro", "bus"}
    assert model_service.bundle["feature_columns"] == FEATURE_COLUMNS


def test_prediction_changes_with_the_hour(client):
    """Changing the hour must change the forecast."""
    on_date = date(2025, 6, 30)
    quiet = model_service.predict("M1", 3, on_date)
    peak = model_service.predict("M1", 8, on_date)
    assert peak["predicted_passengers"] > quiet["predicted_passengers"]


def test_prediction_changes_with_the_route(client):
    on_date = date(2025, 6, 30)
    first = model_service.predict("M1", 8, on_date)
    second = model_service.predict("M5", 8, on_date)
    assert first["route_id"] != second["route_id"]
    assert first["predicted_passengers"] != second["predicted_passengers"]


def test_prediction_changes_with_the_mode(client):
    on_date = date(2025, 6, 30)
    metro = model_service.predict("M1", 8, on_date)
    bus = model_service.predict("B01", 8, on_date)
    assert metro["mode"] == "metro"
    assert bus["mode"] == "bus"
    assert metro["vehicle_capacity"] != bus["vehicle_capacity"]


def test_prediction_changes_with_the_day_of_the_week(client):
    """A weekend forecast must differ from a weekday forecast."""
    monday = date(2025, 6, 30)
    sunday = date(2025, 6, 29)
    weekday = model_service.predict("M1", 8, monday)
    weekend = model_service.predict("M1", 8, sunday)
    assert weekday["predicted_passengers"] != weekend["predicted_passengers"]


def test_prediction_is_not_tied_to_the_training_window(client):
    """A forecast far in the future must still be produced and stay sane."""
    far_future = date.today() + timedelta(days=365)
    result = model_service.predict("M1", 8, far_future)
    assert result["predicted_passengers"] > 0
    assert result["predicted_occupancy_pct"] >= 0


def test_prediction_occupancy_is_consistent_with_the_crowd_level(client):
    result = model_service.predict("M2", 18, date(2025, 6, 30))
    expected = crowd_level_for(result["predicted_occupancy_pct"] / 100.0)
    assert result["crowd_level"] == expected


# --------------------------------------------------------------------------
# The prediction endpoint
# --------------------------------------------------------------------------
def test_prediction_endpoint(client):
    response = client.post(
        "/api/predict", json={"route_id": "M1", "hour": 8, "date": "2025-06-30"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["route_id"] == "M1"
    assert payload["mode"] == "metro"
    assert payload["predicted_passengers"] > 0
    assert payload["crowd_level"] in ("Low", "Moderate", "High", "Critical")
    assert payload["model_name"] in ("random_forest", "gradient_boosting")
    assert "SIMULATED" in payload["data_notice"]


def test_prediction_endpoint_rejects_an_unknown_route(client):
    response = client.post("/api/predict", json={"route_id": "ZZ9", "hour": 8})
    assert response.status_code == 404
    assert "Unknown route" in response.json()["detail"]


def test_prediction_endpoint_rejects_a_mismatched_mode(client):
    response = client.post(
        "/api/predict", json={"route_id": "M1", "hour": 8, "mode": "bus"}
    )
    assert response.status_code == 400


def test_prediction_endpoint_validates_the_hour(client):
    response = client.post("/api/predict", json={"route_id": "M1", "hour": 25})
    assert response.status_code == 422


def test_prediction_day_endpoint(client):
    response = client.get("/api/predict/day?route_id=M1&date=2025-06-30")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["predictions"]) == 24
    assert payload["predictions"][0]["hour"] == 0
    assert payload["predictions"][23]["hour"] == 23


# --------------------------------------------------------------------------
# Alternatives
# --------------------------------------------------------------------------
def test_alternatives_endpoint(client):
    payload = client.get(
        "/api/alternatives?route_id=M1"
        "&origin_id=ST-navacitycentral"
        "&destination_id=ST-whitefielddepot&hour=8"
    ).json()
    assert payload["requested_route"] == "M1"
    assert payload["origin"] == "NavaCity Central"
    for alternative in payload["alternatives"]:
        assert alternative["route_id"] != "M1"
        assert alternative["crowd_level"] in ("Low", "Moderate", "High", "Critical")
        assert alternative["predicted_passengers"] >= 0


def test_alternatives_reject_an_unknown_place(client):
    response = client.get(
        "/api/alternatives?route_id=M1&origin_id=NOPE&destination_id=ST-whitefielddepot"
    )
    assert response.status_code == 404
