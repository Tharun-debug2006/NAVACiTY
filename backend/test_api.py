"""Smoke test of every NavaCity API endpoint (run with the test client)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402

client = TestClient(app)


def show(label: str, response, keys=None) -> None:
    status = response.status_code
    if status >= 400:
        print(f"[{status}] {label}: {response.text[:300]}")
        return
    payload = response.json()
    if keys:
        summary = {key: payload.get(key) for key in keys}
    else:
        summary = payload
    text = json.dumps(summary, indent=2, default=str)
    if len(text) > 900:
        text = text[:900] + " ...(truncated)"
    print(f"[{status}] {label}\n{text}\n")


def main() -> int:
    with client:
        # --- the authority area is protected, so sign in first ---
        login = client.post("/api/auth/login", json={"password": "dumpme"})
        show("POST /api/auth/login", login, ["token_type", "demo_mode", "expires_in"])
        token = login.json()["access_token"] if login.status_code == 200 else ""
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        show("GET /", client.get("/"))
        show("GET /api/health", client.get("/api/health"))
        show("GET /api/auth/config", client.get("/api/auth/config"),
             ["environment", "demo_mode", "configured", "session_minutes"])
        show("GET /api/network", client.get("/api/network"), ["city", "data_notice"])
        show("GET /api/routes?mode=metro", client.get("/api/routes?mode=metro"))
        show("GET /api/places?kind=station", client.get("/api/places?kind=station"))
        show("GET /api/events", client.get("/api/events"), ["count"])
        show("GET /api/crowd-levels", client.get("/api/crowd-levels"))
        show("GET /api/history?limit=3", client.get("/api/history?limit=3"))
        show("GET /api/history/hourly?route_id=M1",
             client.get("/api/history/hourly?route_id=M1"), ["route_id", "mode"])
        show("GET /api/predict?route_id=M1&hour=8",
             client.get("/api/predict?route_id=M1&hour=8"))
        show("POST /api/predict", client.post(
            "/api/predict", json={"route_id": "B03", "hour": 18, "mode": "bus"}))
        show("GET /api/predict/day?route_id=M2",
             client.get("/api/predict/day?route_id=M2"), ["route_id", "date"])
        show("GET /api/crowd-summary?mode=metro",
             client.get("/api/crowd-summary?mode=metro", headers=headers))
        show("GET /api/alerts?limit=3", client.get("/api/alerts?limit=3", headers=headers))
        show("GET /api/authority/stats", client.get("/api/authority/stats", headers=headers),
             ["total_routes", "total_stations", "total_records", "total_passengers",
              "peak_hours"])
        show("GET /api/authority/recommendations?limit=2",
             client.get("/api/authority/recommendations?limit=2", headers=headers),
             ["count", "disclaimer"])
        show("GET /api/alternatives", client.get(
            "/api/alternatives?route_id=M1"
            "&origin_id=ST-navacitycentral"
            "&destination_id=ST-whitefielddepot&hour=8"))
        show("GET /api/model/metrics", client.get("/api/model/metrics", headers=headers),
             ["dataset", "split"])
        show("GET /api/openapi.json", client.get("/openapi.json"), ["openapi"])

        # Error handling
        show("GET /api/predict (unknown route)",
             client.get("/api/predict?route_id=ZZ9&hour=8"))
        show("POST /api/predict (bad hour)",
             client.post("/api/predict", json={"route_id": "M1", "hour": 99}))
        show("GET /api/places (bad mode)", client.get("/api/places?mode=tram"))
        show("GET /api/authority/stats (no token)",
             client.get("/api/authority/stats"))
        show("GET /api/alerts (forged token)",
             client.get("/api/alerts", headers={"Authorization": "Bearer forged.token"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
