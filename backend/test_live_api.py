"""Live end-to-end check against a running backend (http://127.0.0.1:8000).

Usage::

    python backend\\test_live_api.py

The authority endpoints are protected by the backend, so the script signs in
first and sends the session token with the protected requests.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"

#: The password used for the local demo.  Override it with the
#: ``NAVACITY_LIVE_PASSWORD`` environment variable when needed.
PASSWORD = os.environ.get("NAVACITY_LIVE_PASSWORD", "dumpme")


def get(path: str, token: str | None = None):
    request = urllib.request.Request(f"{BASE}{path}")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, json.loads(response.read())


def post(path: str, body: dict, token: str | None = None):
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE}{path}", data=data, headers={"Content-Type": "application/json"}
    )
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, json.loads(response.read())


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        checks.append((label, condition, detail))
        mark = "PASS" if condition else "FAIL"
        print(f"[{mark}] {label}" + (f" - {detail}" if detail else ""))

    status, health = get("/api/health")
    check("GET /api/health", status == 200, f"status={health['status']}")
    check("dataset loaded", health["dataset_loaded"] and health["record_count"] > 0,
          f"records={health['record_count']}")
    check("model loaded", health["model_loaded"])

    status, network = get("/api/network")
    check("GET /api/network", status == 200,
          f"{len(network['metro_lines'])} metro + {len(network['bus_routes'])} bus, "
          f"{len(network['places'])} places")

    # --- the authority area is protected ---
    try:
        get("/api/authority/stats")
        check("authority stats without a token -> 401", False, "no error raised")
    except urllib.error.HTTPError as exc:
        check("authority stats without a token -> 401", exc.code == 401, f"got {exc.code}")

    status, auth_config = get("/api/auth/config")
    check("GET /api/auth/config", status == 200,
          f"environment={auth_config['environment']}, demo={auth_config['demo_mode']}")

    status, session = post("/api/auth/login", {"password": PASSWORD})
    check("POST /api/auth/login", status == 200, f"demo_mode={session.get('demo_mode')}")
    token = session["access_token"]

    status, stats = get("/api/authority/stats", token=token)
    check("GET /api/authority/stats (with token)", status == 200,
          f"{stats['total_routes']} routes, {stats['total_passengers']:,} passengers, "
          f"{len(stats['recommendations'])} recommendations")

    status, alerts = get("/api/alerts?limit=5", token=token)
    check("GET /api/alerts", status == 200 and alerts["count"] > 0,
          f"{alerts['count']} alerts above {alerts['threshold_pct']}%")

    status, metrics = get("/api/model/metrics", token=token)
    check("GET /api/model/metrics", status == 200,
          "metro R2=" + str(round(metrics["modes"]["metro"]["time_ordered_metrics"]["r2"], 4)))

    status, pred_a = post("/api/predict",
                           {"route_id": "M1", "hour": 8, "date": "2025-06-30"})
    check("POST /api/predict M1 08:00", status == 200,
          f"{pred_a['predicted_passengers']} pax, {pred_a['crowd_level']}, "
          f"{pred_a['predicted_occupancy_pct']}%")

    status, pred_b = post("/api/predict",
                           {"route_id": "M1", "hour": 18, "date": "2025-06-30"})
    check("prediction changes with the hour",
          pred_a["predicted_passengers"] != pred_b["predicted_passengers"],
          f"08:00={pred_a['predicted_passengers']} 18:00={pred_b['predicted_passengers']}")

    status, pred_c = post("/api/predict",
                           {"route_id": "B01", "hour": 8, "date": "2025-06-30"})
    check("prediction changes with the mode",
          pred_c["mode"] == "bus" and pred_c["predicted_passengers"] != pred_a["predicted_passengers"],
          f"B01={pred_c['predicted_passengers']} pax ({pred_c['crowd_level']})")

    status, pred_d = post("/api/predict",
                           {"route_id": "M1", "hour": 8, "date": "2025-06-29"})
    check("prediction changes with the day",
          pred_d["predicted_passengers"] != pred_a["predicted_passengers"],
          f"Sunday={pred_d['predicted_passengers']} pax")

    status, pred_new = post("/api/predict",
                             {"route_id": "B18", "hour": 8, "date": "2025-06-30"})
    check("a new bus route (B18) can be predicted", status == 200,
          f"{pred_new['predicted_passengers']} pax ({pred_new['crowd_level']})")

    status, summary = get("/api/crowd-summary", token=token)
    check("GET /api/crowd-summary", status == 200,
          f"{summary['total_records']} records, {summary['overcrowded_records']} overcrowded")

    status, day = get("/api/predict/day?route_id=M1")
    check("GET /api/predict/day", status == 200 and len(day["predictions"]) == 24)

    status, history = get("/api/history?limit=10")
    check("GET /api/history", status == 200 and history["count"] == 10)

    status, hourly = get("/api/history/hourly?route_id=M1")
    check("GET /api/history/hourly", status == 200 and len(hourly["points"]) == 24)

    # --- logout invalidates the token ---
    status, _ = post("/api/auth/logout", {}, token=token)
    check("POST /api/auth/logout", status == 200)
    try:
        get("/api/authority/stats", token=token)
        check("the token is rejected after the logout", False, "no error raised")
    except urllib.error.HTTPError as exc:
        check("the token is rejected after the logout", exc.code == 401, f"got {exc.code}")

    # --- error handling ---
    try:
        get("/api/predict?route_id=ZZ9&hour=8")
        check("unknown route -> 404", False, "no error raised")
    except urllib.error.HTTPError as exc:
        check("unknown route -> 404", exc.code == 404, f"got {exc.code}")

    try:
        post("/api/predict", {"route_id": "M1", "hour": 99})
        check("invalid hour -> 422", False, "no error raised")
    except urllib.error.HTTPError as exc:
        check("invalid hour -> 422", exc.code == 422, f"got {exc.code}")

    try:
        get("/api/routes?mode=tram")
        check("invalid mode -> 422", False, "no error raised")
    except urllib.error.HTTPError as exc:
        check("invalid mode -> 422", exc.code == 422, f"got {exc.code}")

    passed = sum(1 for _, ok, _ in checks if ok)
    print("=" * 60)
    print(f"{passed}/{len(checks)} live checks passed")
    print("=" * 60)
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
