"""SQLite persistence for the NavaCity backend.

Three groups of tables are used:

``places``   every metro station and bus stop of the (fictional) network
``routes``   every metro line and bus route
``records``  the SIMULATED hourly demand observations

The network tables are seeded from :mod:`navacity_core.network`; the records
table is seeded from the generated CSV dataset.  Everything in here is
simulated data.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    """Declarative base class for the NavaCity tables."""


class Place(Base):
    """A metro station or a bus stop."""

    __tablename__ = "places"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # "station" | "stop"
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    zone: Mapped[int] = mapped_column(Integer, default=2)
    is_interchange: Mapped[bool] = mapped_column(Boolean, default=False)
    metro_lines: Mapped[str] = mapped_column(String(120), default="")
    bus_routes: Mapped[str] = mapped_column(String(200), default="")


class Route(Base):
    """A metro line or a bus route."""

    __tablename__ = "routes"

    id: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    mode: Mapped[str] = mapped_column(String(10), index=True)  # "metro" | "bus"
    color: Mapped[str] = mapped_column(String(10))
    base_frequency: Mapped[int] = mapped_column(Integer)
    vehicle_capacity: Mapped[int] = mapped_column(Integer)
    travel_minutes: Mapped[int] = mapped_column(Integer)
    popularity: Mapped[float] = mapped_column(Float)
    stops: Mapped[str] = mapped_column(String(400), default="")  # comma separated ids


class DemandRecord(Base):
    """One SIMULATED hourly observation of a route segment."""

    __tablename__ = "records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    date: Mapped[str] = mapped_column(String(10), index=True)
    hour: Mapped[int] = mapped_column(Integer, index=True)
    day_of_week: Mapped[int] = mapped_column(Integer)
    day_name: Mapped[str] = mapped_column(String(12))
    is_weekend: Mapped[bool] = mapped_column(Boolean)
    is_holiday: Mapped[bool] = mapped_column(Boolean)
    holiday_name: Mapped[str] = mapped_column(String(60), default="")
    day_type: Mapped[str] = mapped_column(String(10))
    mode: Mapped[str] = mapped_column(String(10), index=True)
    route_id: Mapped[str] = mapped_column(String(8), ForeignKey("routes.id"), index=True)
    route_name: Mapped[str] = mapped_column(String(80))
    segment_id: Mapped[str] = mapped_column(String(16), index=True)
    origin_id: Mapped[str] = mapped_column(String(32), index=True)
    origin_name: Mapped[str] = mapped_column(String(80))
    dest_id: Mapped[str] = mapped_column(String(32), index=True)
    dest_name: Mapped[str] = mapped_column(String(80))
    passenger_count: Mapped[int] = mapped_column(Integer, index=True)
    vehicle_capacity: Mapped[int] = mapped_column(Integer)
    service_frequency: Mapped[int] = mapped_column(Integer)
    hourly_capacity: Mapped[int] = mapped_column(Integer)
    occupancy_pct: Mapped[float] = mapped_column(Float)
    crowd_level: Mapped[str] = mapped_column(String(12), index=True)
    weather: Mapped[str] = mapped_column(String(16))
    traffic_level: Mapped[str] = mapped_column(String(12))
    special_event: Mapped[bool] = mapped_column(Boolean)
    waiting_time_min: Mapped[float] = mapped_column(Float)
    travel_time_min: Mapped[float] = mapped_column(Float)
    is_overcrowded: Mapped[bool] = mapped_column(Boolean, index=True)


Index("ix_records_route_hour", DemandRecord.route_id, DemandRecord.hour)
Index("ix_records_mode_date", DemandRecord.mode, DemandRecord.date)


# --------------------------------------------------------------------------
# Engine / session
# --------------------------------------------------------------------------
settings.db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    """Enable foreign keys and use a fast journal mode on SQLite."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager for scripts that need a session outside a request."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
