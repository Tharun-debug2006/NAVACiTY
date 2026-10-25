"""Seed the SQLite database of the NavaCity backend with the simulated data.

Usage (from the repository root, Windows PowerShell)::

    python backend\\seed_database.py

The script

* creates the ``places``, ``routes`` and ``records`` tables,
* fills them from ``navacity_core.network`` and from the generated CSV
  dataset (``data/generated/navacity_transport.csv``).

It is safe to run it again: an existing database is emptied and rebuilt.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402

from backend.app.config import settings  # noqa: E402
from backend.app.database import Base, DemandRecord, Place, Route, engine  # noqa: E402
from navacity_core.network import build_network  # noqa: E402


def seed_network(session) -> tuple[int, int]:
    """Insert the stations, stops and routes.  Returns (places, routes)."""
    network = build_network()

    for place in network["places"]:
        session.add(
            Place(
                id=place["id"],
                name=place["name"],
                kind=place["kind"],
                x=float(place["x"]),
                y=float(place["y"]),
                zone=int(place["zone"]),
                is_interchange=bool(place["is_interchange"]),
                metro_lines=",".join(place["metro_lines"]),
                bus_routes=",".join(place["bus_routes"]),
            )
        )

    for line in network["metro_lines"]:
        session.add(
            Route(
                id=line["id"],
                name=line["name"],
                mode="metro",
                color=line["color"],
                base_frequency=int(line["base_frequency"]),
                vehicle_capacity=int(line["vehicle_capacity"]),
                travel_minutes=int(line["travel_minutes"]),
                popularity=float(line["popularity"]),
                stops=",".join(line["stations"]),
            )
        )

    for route in network["bus_routes"]:
        session.add(
            Route(
                id=route["id"],
                name=route["name"],
                mode="bus",
                color=route["color"],
                base_frequency=int(route["base_frequency"]),
                vehicle_capacity=int(route["vehicle_capacity"]),
                travel_minutes=int(route["travel_minutes"]),
                popularity=float(route["popularity"]),
                stops=",".join(route["stops"]),
            )
        )

    session.flush()
    return len(network["places"]), len(network["metro_lines"]) + len(network["bus_routes"])


def seed_records(session, csv_path: Path, chunk_size: int = 10000) -> int:
    """Insert the simulated hourly demand observations.  Returns the row count.

    The rows are written with a single ``executemany`` per chunk, which is
    roughly an order of magnitude faster than the ORM on 70 000 rows.
    """
    df = pd.read_csv(csv_path)

    def to_bool(value) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "1", "yes")

    columns = [
        "timestamp", "date", "hour", "day_of_week", "day_name", "is_weekend",
        "is_holiday", "holiday_name", "day_type", "mode", "route_id",
        "route_name", "segment_id", "origin_id", "origin_name", "dest_id",
        "dest_name", "passenger_count", "vehicle_capacity", "service_frequency",
        "hourly_capacity", "occupancy_pct", "crowd_level", "weather",
        "traffic_level", "special_event", "waiting_time_min", "travel_time_min",
        "is_overcrowded",
    ]
    insert = DemandRecord.__table__.insert()

    total = 0
    for start in range(0, len(df), chunk_size):
        chunk = df.iloc[start:start + chunk_size]
        payload = []
        for record in chunk.to_dict("records"):
            payload.append(
                {
                    "timestamp": datetime.fromisoformat(str(record["timestamp"])),
                    "date": str(record["date"]),
                    "hour": int(record["hour"]),
                    "day_of_week": int(record["day_of_week"]),
                    "day_name": str(record["day_name"]),
                    "is_weekend": to_bool(record["is_weekend"]),
                    "is_holiday": to_bool(record["is_holiday"]),
                    "holiday_name": str(
                        record.get("holiday_name", "") or "Not a holiday"
                    ),
                    "day_type": str(record["day_type"]),
                    "mode": str(record["mode"]),
                    "route_id": str(record["route_id"]),
                    "route_name": str(record["route_name"]),
                    "segment_id": str(record["segment_id"]),
                    "origin_id": str(record["origin_id"]),
                    "origin_name": str(record["origin_name"]),
                    "dest_id": str(record["dest_id"]),
                    "dest_name": str(record["dest_name"]),
                    "passenger_count": int(record["passenger_count"]),
                    "vehicle_capacity": int(record["vehicle_capacity"]),
                    "service_frequency": int(record["service_frequency"]),
                    "hourly_capacity": int(record["hourly_capacity"]),
                    "occupancy_pct": float(record["occupancy_pct"]),
                    "crowd_level": str(record["crowd_level"]),
                    "weather": str(record["weather"]),
                    "traffic_level": str(record["traffic_level"]),
                    "special_event": to_bool(record["special_event"]),
                    "waiting_time_min": float(record["waiting_time_min"]),
                    "travel_time_min": float(record["travel_time_min"]),
                    "is_overcrowded": to_bool(record["is_overcrowded"]),
                }
            )
        session.execute(insert, payload)
        session.commit()
        total += len(payload)
        print(f"    ... {total:,} / {len(df):,} records inserted", flush=True)

    return total


def main() -> int:
    csv_path = settings.dataset_csv
    if not csv_path.exists():
        print(
            f"ERROR: dataset not found at {csv_path}.\n"
            "Run 'python ml\\generate_dataset.py' first.",
            file=sys.stderr,
        )
        return 2

    print(f"Rebuilding the SQLite database at {settings.db_path}")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    from backend.app.database import SessionLocal

    session = SessionLocal()
    try:
        places, routes = seed_network(session)
        print(f"  inserted {places} stations/stops and {routes} routes")
        records = seed_records(session, csv_path)
        print(f"  inserted {records:,} simulated demand records")
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print("Database seeded successfully (SIMULATED data).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
