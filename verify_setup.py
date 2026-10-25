"""Final verification: check that every deliverable exists and is consistent.

Run from the repository root::

    python verify_setup.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402

from navacity_core.config import (  # noqa: E402
    ARTIFACTS_DIR,
    CROWD_LEVELS,
    DATASET_CSV,
    METRICS_JSON,
    MODEL_BUNDLE,
    NETWORK_JSON,
)
from navacity_core.features import FEATURE_COLUMNS, LEAKY_COLUMNS  # noqa: E402
from navacity_core.network import build_network  # noqa: E402

checks: list[tuple[str, bool, str]] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    checks.append((label, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" - {detail}" if detail else ""))


def main() -> int:
    # 1. The dataset
    check("dataset CSV exists", DATASET_CSV.exists(), str(DATASET_CSV))
    df = pd.read_csv(DATASET_CSV)
    check("dataset has >= 10 000 rows", len(df) >= 10_000, f"{len(df):,} rows")
    required = {
        "timestamp", "date", "hour", "day_of_week", "is_weekend", "mode",
        "route_id", "origin_id", "dest_id", "passenger_count", "vehicle_capacity",
        "occupancy_pct", "weather", "traffic_level", "is_holiday",
        "special_event", "service_frequency", "waiting_time_min", "crowd_level",
    }
    missing = required - set(df.columns)
    check("dataset has all the required columns", not missing, f"missing: {sorted(missing)}")
    check("dataset has no missing values", int(df.isna().sum().sum()) == 0)
    check(
        "dataset contains both transport modes",
        set(df["mode"]) == {"metro", "bus"},
        f"metro={int((df['mode']=='metro').sum()):,} bus={int((df['mode']=='bus').sum()):,}",
    )
    check(
        "crowd levels are within the defined set",
        set(df["crowd_level"]) <= set(CROWD_LEVELS),
        str(sorted(set(df["crowd_level"]))),
    )

    # 2. The network
    network = build_network()
    check("network has 6 metro lines", len(network["metro_lines"]) == 6)
    check("network has 18 bus routes", len(network["bus_routes"]) == 18)
    check("network has 46 places", len(network["places"]) == 46,
          f"{len(network['places'])}")
    check("network has 132 segments", len(network["segments"]) == 132,
          f"{len(network['segments'])}")
    check("network JSON exists", NETWORK_JSON.exists())

    # Every route must be present in the popularity and travel-time tables,
    # otherwise the simulator would raise a KeyError.
    from navacity_core.network import ROUTE_POPULARITY, ROUTE_TRAVEL_MINUTES

    all_route_ids = (
        [line["id"] for line in network["metro_lines"]]
        + [route["id"] for route in network["bus_routes"]]
    )
    check(
        "every route has a popularity weight",
        set(all_route_ids) <= set(ROUTE_POPULARITY),
        f"missing: {sorted(set(all_route_ids) - set(ROUTE_POPULARITY))}",
    )
    check(
        "every route has a travel time",
        set(all_route_ids) <= set(ROUTE_TRAVEL_MINUTES),
        f"missing: {sorted(set(all_route_ids) - set(ROUTE_TRAVEL_MINUTES))}",
    )

    # 3. The model artefacts
    check("model bundle exists", MODEL_BUNDLE.exists(),
          f"{MODEL_BUNDLE.stat().st_size // 1024} KB" if MODEL_BUNDLE.exists() else "")
    check("metrics JSON exists", METRICS_JSON.exists())
    metrics = json.loads(METRICS_JSON.read_text(encoding="utf-8"))
    for mode in ("metro", "bus"):
        m = metrics["modes"][mode]
        check(
            f"{mode} metrics are real numbers",
            m["time_ordered_metrics"]["mae"] > 0
            and m["time_ordered_metrics"]["rmse"] > 0
            and m["time_ordered_metrics"]["r2"] is not None,
            f"MAE={m['time_ordered_metrics']['mae']:.2f} "
            f"RMSE={m['time_ordered_metrics']['rmse']:.2f} "
            f"R2={m['time_ordered_metrics']['r2']:.4f} "
            f"model={m['best_model']}",
        )
        check(
            f"{mode} has both baselines compared",
            set(m["all_model_metrics"]) == {"random_forest", "gradient_boosting"},
        )
    check(
        "the split is time ordered",
        "time_ordered" in metrics["split"]["strategy"],
        metrics["split"]["strategy"],
    )
    check(
        "the leaky columns are documented as excluded",
        set(metrics["features"]["excluded_leaky_columns"]) == set(LEAKY_COLUMNS),
    )
    check(
        "no leaky column is used as a feature",
        not set(FEATURE_COLUMNS) & set(LEAKY_COLUMNS),
    )

    # 4. The evaluation plots
    for plot in (
        "actual_vs_predicted_metro.png", "actual_vs_predicted_bus.png",
        "residuals_metro.png", "residuals_bus.png",
        "feature_importance.png", "forecast_vs_history.png",
    ):
        path = ARTIFACTS_DIR / plot
        check(f"plot {plot}", path.exists() and path.stat().st_size > 10_000,
              f"{path.stat().st_size // 1024} KB" if path.exists() else "missing")

    # 5. The project files
    for rel in (
        "README.md", "pytest.ini", ".gitignore", ".env.example",
        "backend/requirements.txt", "backend/seed_database.py", "backend/app/main.py",
        "backend/app/api.py", "backend/app/schemas.py", "backend/app/database.py",
        "backend/tests/conftest.py", "backend/tests/test_api.py",
        "backend/tests/test_prediction.py", "backend/tests/test_journey.py",
        "ml/generate_dataset.py", "ml/train_model.py", "ml/requirements.txt",
        "frontend/package.json", "frontend/vite.config.js", "frontend/index.html",
        "frontend/tailwind.config.js",
        "frontend/src/App.jsx", "frontend/src/main.jsx", "frontend/src/api/client.js",
        "frontend/src/lib/format.js", "frontend/src/styles/tokens.css",
        "frontend/src/pages/PublicDashboard.jsx",
        "frontend/src/pages/AuthorityDashboard.jsx",
        "frontend/src/components/CrowdBadge.jsx",
        "frontend/src/components/TransitMap.jsx",
        "frontend/src/components/States.jsx",
        "frontend/src/components/AnswerCard.jsx",
        "frontend/src/components/AlternativeCard.jsx",
        "frontend/src/components/StationPicker.jsx",
        "frontend/src/components/ModeSwitch.jsx",
        "frontend/src/components/ChartCard.jsx",
        "frontend/src/components/StatCard.jsx",
        "frontend/src/components/DataNotice.jsx",
        "frontend/src/components/CollapsibleSection.jsx",
        "docs/baseline_report.md", "docs/issue_log.md", "docs/design_system.md",
        "navacity_core/config.py", "navacity_core/network.py", "navacity_core/events.py",
        "navacity_core/simulator.py", "navacity_core/features.py",
    ):
        check(f"file {rel}", (REPO_ROOT / rel).exists())

    # 6. The database
    db = REPO_ROOT / "data" / "navacity.db"
    check("SQLite database exists", db.exists(),
          f"{db.stat().st_size // 1024} KB" if db.exists() else "")

    # 6b. The secrets must never be committed (C7).
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    check(".env is ignored by git", ".env" in gitignore.splitlines())
    check(
        ".env.example is NOT ignored by git",
        "!.env.example" in gitignore,
    )
    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    demo_lines = [
        line
        for line in env_example.splitlines()
        if line.strip().startswith("NAVACITY_AUTH_PASSWORD=")
    ]
    check(
        "the demo password is commented out in .env.example",
        not demo_lines,
        f"active lines: {demo_lines}",
    )
    check(
        "no committed file contains a real .env",
        not (REPO_ROOT / ".env").exists()
        or ".env" in gitignore,
    )

    # 6c. The data granularity must be stated consistently (C3).
    from navacity_core.config import SAMPLES_PER_SEGMENT_DAY

    check(
        "the dataset granularity is 4 observations per stretch and day",
        SAMPLES_PER_SEGMENT_DAY == 4,
        f"SAMPLES_PER_SEGMENT_DAY={SAMPLES_PER_SEGMENT_DAY}",
    )
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    check(
        "the README states the data granularity",
        "4 observations per route-stretch per day" in readme,
    )
    check(
        "the README does not call the rows 'hourly observations'",
        "simulated hourly observations" not in readme,
    )

    # 7. No hard-coded secrets or paid services
    secrets_found = []
    for rel in ("frontend/src", "backend/app", "navacity_core", "ml"):
        for path in (REPO_ROOT / rel).rglob("*"):
            if path.suffix not in (".py", ".jsx", ".js", ".css"):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for needle in ("api_key", "apikey", "secret_key", "sk-", "openai", "google_maps"):
                if needle in text:
                    secrets_found.append(f"{needle} in {path.relative_to(REPO_ROOT)}")
    check("no API keys or paid services are referenced", not secrets_found,
          "; ".join(secrets_found))

    passed = sum(1 for _, ok, _ in checks if ok)
    print("=" * 70)
    print(f"{passed}/{len(checks)} verification checks passed")
    print("=" * 70)
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
