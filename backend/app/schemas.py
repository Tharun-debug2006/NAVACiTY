"""Pydantic request / response models for the NavaCity API."""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

Mode = Literal["metro", "bus"]
CrowdLevel = Literal["Low", "Moderate", "High", "Critical"]
Weather = Literal["clear", "cloudy", "light_rain", "heavy_rain", "fog"]
Traffic = Literal["light", "moderate", "heavy", "severe"]


# --------------------------------------------------------------------------
# Authority authentication
# --------------------------------------------------------------------------
class LoginRequest(BaseModel):
    """The body of ``POST /api/auth/login``."""

    password: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="The transport-authority password (NAVACITY_AUTH_PASSWORD).",
    )


class SessionInfo(BaseModel):
    """The identity of the signed-in authority operator."""

    role: str
    issued_at: int
    expires_at: int
    session_id: str


class LoginResponse(BaseModel):
    """The answer of a successful login."""

    access_token: str
    token_type: str = "bearer"
    expires_at: int
    expires_in: int
    session: SessionInfo
    demo_mode: bool
    message: str


class LogoutResponse(BaseModel):
    """The answer of a logout."""

    revoked: bool
    message: str


class AuthConfigResponse(BaseModel):
    """Public description of the authentication setup (no secrets)."""

    environment: str
    demo_mode: bool
    configured: bool
    session_minutes: int
    error: str | None = None
    notice: str


# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    database: str
    dataset_loaded: bool
    model_loaded: bool
    network_loaded: bool
    record_count: int
    data_notice: str
    authority_auth_configured: bool = False


# --------------------------------------------------------------------------
# Network
# --------------------------------------------------------------------------
class Place(BaseModel):
    id: str
    name: str
    kind: str
    x: float
    y: float
    zone: int
    is_interchange: bool
    metro_lines: list[str]
    bus_routes: list[str]


class RouteSummary(BaseModel):
    id: str
    name: str
    mode: Mode
    color: str
    base_frequency: int
    vehicle_capacity: int
    travel_minutes: int
    popularity: float
    stops: list[str]
    stop_names: list[str]


class NetworkResponse(BaseModel):
    city: str
    data_notice: str
    metro_lines: list[RouteSummary]
    bus_routes: list[RouteSummary]
    places: list[Place]


# --------------------------------------------------------------------------
# History
# --------------------------------------------------------------------------
class HistoryPoint(BaseModel):
    timestamp: datetime
    date: str
    hour: int
    route_id: str
    route_name: str
    segment_id: str
    origin_name: str
    dest_name: str
    passenger_count: int
    occupancy_pct: float
    crowd_level: CrowdLevel
    service_frequency: int
    waiting_time_min: float
    weather: str
    traffic_level: str
    is_overcrowded: bool
    special_event: bool


class HistoryResponse(BaseModel):
    count: int
    data_notice: str
    records: list[HistoryPoint]


class HourlyPoint(BaseModel):
    hour: int
    mean_passengers: float
    mean_occupancy_pct: float
    max_passengers: int
    crowd_level: CrowdLevel
    records: int


class HourlyProfileResponse(BaseModel):
    route_id: str
    mode: Mode
    date: str
    data_notice: str
    points: list[HourlyPoint]


# --------------------------------------------------------------------------
# Prediction
# --------------------------------------------------------------------------
class PredictionRequest(BaseModel):
    """Request body of the demand prediction endpoint."""

    route_id: str = Field(..., description="Metro line (M1-M6) or bus route (B01-B18)")
    hour: int = Field(..., ge=0, le=23, description="Hour of day, 0-23")
    date: Optional[date_type] = Field(
        None, description="Day of the forecast; defaults to the next weekday"
    )
    mode: Optional[Mode] = Field(None, description="Optional transport mode filter")
    segment_id: Optional[str] = Field(None, description="Optional route segment")
    origin_id: Optional[str] = Field(
        None, description="Place the traveller starts from (station / stop id)"
    )
    destination_id: Optional[str] = Field(
        None, description="Place the traveller travels to (station / stop id)"
    )
    weather: Optional[Weather] = Field(None, description="Expected weather")
    traffic_level: Optional[Traffic] = Field(None, description="Expected traffic")
    special_event: bool = Field(False, description="Whether an event affects the route")

    @field_validator("route_id")
    @classmethod
    def _strip_route(cls, value: str) -> str:
        return value.strip().upper()


class JourneyInfo(BaseModel):
    """The journey the forecast was made for."""

    origin_id: str
    origin_name: str
    destination_id: str
    destination_name: str
    segment_id: str
    segment_origin_name: str
    segment_dest_name: str
    ride_minutes: Optional[float] = None
    traffic_factor: float = 1.0


class PredictionResponse(BaseModel):
    route_id: str
    route_name: str
    mode: Mode
    segment_id: str
    origin_name: str
    dest_name: str
    date: str
    hour: int
    predicted_passengers: int
    predicted_occupancy_pct: float
    crowd_level: CrowdLevel
    is_overcrowded: bool
    service_frequency: int
    vehicle_capacity: int
    hourly_capacity: int
    waiting_time_min: float
    travel_time_min: float
    segment_travel_time_min: float
    total_journey_time_min: float
    journey: Optional[JourneyInfo] = None
    model_name: str
    assumptions: str
    data_notice: str
    # Whether the requested date lies outside the simulated (training) window.
    is_extrapolation: bool = False
    extrapolation_notice: Optional[str] = None
    supported_date_range: dict = {}


# --------------------------------------------------------------------------
# Crowd summary / alerts
# --------------------------------------------------------------------------
class CrowdSummaryEntry(BaseModel):
    crowd_level: CrowdLevel
    count: int
    share_pct: float
    mean_occupancy_pct: float


class CrowdSummaryResponse(BaseModel):
    mode: Optional[Mode]
    route_id: Optional[str]
    total_records: int
    data_notice: str
    levels: list[CrowdSummaryEntry]
    average_occupancy_pct: float
    overcrowded_records: int
    overcrowded_share_pct: float


class OvercrowdingAlert(BaseModel):
    route_id: str
    route_name: str
    mode: Mode
    segment_id: str
    origin_name: str
    dest_name: str
    date: str
    hour: int
    mean_passengers: float
    mean_occupancy_pct: float
    peak_occupancy_pct: float
    crowd_level: CrowdLevel
    severity: Literal["warning", "critical"]
    affected_records: int


class AlertsResponse(BaseModel):
    count: int
    threshold_pct: float
    data_notice: str
    alerts: list[OvercrowdingAlert]


# --------------------------------------------------------------------------
# Authority dashboard
# --------------------------------------------------------------------------
class KpiCard(BaseModel):
    key: str
    label: str
    value: float
    unit: str
    detail: str


class ModeComparison(BaseModel):
    mode: Mode
    total_passengers: int
    mean_passengers: float
    mean_occupancy_pct: float
    routes: int
    records: int
    share_pct: float
    # Comparable metrics (the primary comparison between the two modes).
    overcrowded_records: int = 0
    overcrowded_share_pct: float = 0.0
    passengers_per_vehicle: float = 0.0
    mean_vehicles_per_hour: float = 0.0
    mean_hourly_capacity: float = 0.0
    share_of_records_pct: float = 0.0


class RouteAnalytics(BaseModel):
    route_id: str
    route_name: str
    mode: Mode
    total_passengers: int
    mean_passengers: float
    peak_hour: int
    peak_passengers: float
    mean_occupancy_pct: float
    overcrowded_records: int
    busiest_segment: str
    overcrowded_share_pct: float
    # The busiest stretch of the route, by name (for the planner).
    busiest_segment_names: str = ""
    # Passengers per vehicle per hour at the peak: comparable across modes.
    peak_load_per_vehicle: float = 0.0
    vehicle_capacity: int = 0
    peak_occupancy_pct: float = 0.0


class HourlyAnalytics(BaseModel):
    hour: int
    mean_passengers: float
    mean_occupancy_pct: float
    metro_passengers: float
    bus_passengers: float
    crowd_level: CrowdLevel
    # The share of the observations of that hour that are at or above the
    # 80 % overcrowding threshold.
    overcrowded_share_pct: float = 0.0
    observations: int = 0


class ServiceRecommendation(BaseModel):
    route_id: str
    route_name: str
    mode: Mode
    hour: int
    current_frequency: int
    recommended_frequency: int
    change: int
    reason: str
    confidence: Literal["low", "medium", "high"]
    disclaimer: str
    # The rule that produced the recommendation, stated explicitly.
    rule: str = ""
    # The stretch of the route the recommendation is about.
    segment_id: str = ""
    segment_names: str = ""


class AuthorityStatsResponse(BaseModel):
    generated_for: str
    data_notice: str
    total_routes: int
    total_stations: int
    total_stops: int
    total_records: int
    total_passengers: int
    average_occupancy_pct: float
    overcrowded_records: int
    mode: Optional[Mode] = None
    kpis: list[KpiCard]
    mode_comparison: list[ModeComparison]
    route_analytics: list[RouteAnalytics]
    hourly_analytics: list[HourlyAnalytics]
    weekday_weekend_profile: list[dict] = []
    peak_hours: list[int]
    recommendations: list[ServiceRecommendation]
    data_period: dict = {}


# --------------------------------------------------------------------------
# Alternatives
# --------------------------------------------------------------------------
class AlternativeRoute(BaseModel):
    route_id: str
    route_name: str
    mode: Mode
    segment_id: str
    origin_name: str
    dest_name: str
    predicted_passengers: int
    predicted_occupancy_pct: float
    crowd_level: CrowdLevel
    waiting_time_min: float
    travel_time_min: float
    total_journey_time_min: float
    service_frequency: int
    direct: bool
    transfers: int
    reason: str


class AlternativesResponse(BaseModel):
    origin: str
    destination: str
    requested_route: str
    hour: int
    date: str
    data_notice: str
    # The journey time of the route the traveller asked about, so that every
    # alternative can be compared against it on the same basis.
    requested_total_journey_time_min: Optional[float] = None
    requested_crowd_level: Optional[CrowdLevel] = None
    alternatives: list[AlternativeRoute]


# --------------------------------------------------------------------------
# Model metrics
# --------------------------------------------------------------------------
class ModelMetricsResponse(BaseModel):
    data_notice: str
    trained_at: Optional[str] = None
    dataset: dict = {}
    split: dict = {}
    modes: dict = {}
    mean_feature_importance: dict = {}
    crowd_thresholds: list[dict] = []
