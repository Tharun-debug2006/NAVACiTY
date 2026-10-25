"""All HTTP endpoints of the NavaCity backend.

The endpoints are grouped in one router so that the Swagger UI shows a
single, clearly documented API.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from navacity_core.config import (
    CROWD_LEVELS,
    OBSERVED_MONTHS,
    OVERCROWDING_ALERT_THRESHOLD,
    SIM_END_DATE,
    SIM_START_DATE,
    crowd_level_bounds,
    is_within_observed_months,
    is_within_simulated_window,
)
from navacity_core.events import SPECIAL_EVENTS

from .auth import auth_service, client_ip, require_authority
from .config import settings
from .database import DemandRecord, Place, Route, get_db
from .schemas import (
    AlternativesResponse,
    AlertsResponse,
    AuthorityStatsResponse,
    AuthConfigResponse,
    CrowdSummaryResponse,
    HealthResponse,
    HistoryPoint,
    HistoryResponse,
    HourlyProfileResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    ModelMetricsResponse,
    NetworkResponse,
    Place as PlaceSchema,
    PredictionRequest,
    PredictionResponse,
    RouteSummary,
    SessionInfo,
)
from .services.alternatives_service import suggest_alternatives
from .services.analytics_service import (
    DATA_NOTICE,
    authority_stats,
    count_records,
    crowd_summary,
    dataset_date_range,
    hourly_profile,
    overcrowding_alerts,
)
from .services.model_service import model_service
from .security import SessionPayload

router = APIRouter()

# --------------------------------------------------------------------------
# Authority authentication
# --------------------------------------------------------------------------
AUTH_NOTICE = (
    "The authority endpoints are protected. Sign in with the transport "
    "authority password to read the statistics, the recommendations and the "
    "model evaluation."
)


@router.get("/auth/config", response_model=AuthConfigResponse, tags=["Authority"])
def get_auth_config() -> AuthConfigResponse:
    """Describe the authentication setup (no secret is ever returned)."""
    info = auth_service.describe()
    if info["demo_mode"]:
        # The demo password is a well-known constant of this project, but it is
        # deliberately NOT echoed back by an unauthenticated endpoint: a
        # public response must never disclose a credential.  The login screen
        # only learns *that* the server runs in demo mode.
        notice = (
            "Demo mode: the server accepts the well-known local demo "
            "password because NAVACITY_ENV is 'local'. Never run the server in "
            "this mode in a real deployment."
        )
    elif not info["configured"]:
        notice = (
            "Authority authentication is not configured. Set "
            "NAVACITY_AUTH_PASSWORD before starting the server."
        )
    else:
        notice = (
            f"Authority sessions last {info['session_minutes']} minutes and are "
            "validated by the server on every request."
        )
    return AuthConfigResponse(notice=notice, **info)


@router.post("/auth/login", response_model=LoginResponse, tags=["Authority"])
def login(payload: LoginRequest, request: Request) -> LoginResponse:
    """Exchange the authority password for a short-lived session token."""
    if not auth_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Authority authentication is not configured: "
                f"{auth_service.error}"
            ),
        )
    if not auth_service.check_password(payload.password):
        # A wrong password is answered with a generic message so that the
        # API does not reveal whether the account exists.
        print(
            f"[NavaCity] rejected authority login from {client_ip(request)}",
            file=sys.stderr,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authority password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token, session = auth_service.create_session()
    print(
        f"[NavaCity] authority login accepted from {client_ip(request)}",
        file=sys.stderr,
    )
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_at=session.expires_at,
        expires_in=session.expires_at - session.issued_at,
        session=SessionInfo(
            role=session.role,
            issued_at=session.issued_at,
            expires_at=session.expires_at,
            session_id=session.session_id,
        ),
        demo_mode=auth_service.is_demo_mode,
        message=(
            "Signed in to the transport-authority dashboard. The session is "
            "validated by the server on every request."
        ),
    )


@router.post("/auth/logout", response_model=LogoutResponse, tags=["Authority"])
def logout(session_payload: SessionPayload = Depends(require_authority)) -> LogoutResponse:
    """Invalidate the current session immediately."""
    revoked = auth_service.revoke_session(session_payload.session_id)
    return LogoutResponse(
        revoked=revoked,
        message="Signed out. The session token is no longer accepted.",
    )


@router.get("/auth/session", response_model=SessionInfo, tags=["Authority"])
def current_session(
    session_payload: SessionPayload = Depends(require_authority),
) -> SessionInfo:
    """Return the identity of the current session (used to restore a login)."""
    return SessionInfo(
        role=session_payload.role,
        issued_at=session_payload.issued_at,
        expires_at=session_payload.expires_at,
        session_id=session_payload.session_id,
    )


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _next_forecast_date() -> date:
    """Default forecast day: the next weekday, starting tomorrow."""
    target = date.today() + timedelta(days=1)
    while target.weekday() >= 5:
        target += timedelta(days=1)
    return target


def _route_exists(session: Session, route_id: str) -> Route:
    route = session.get(Route, route_id)
    if route is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Unknown route '{route_id}'. Use /api/network to list the "
                f"available routes."
            ),
        )
    return route


# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------
@router.get("/health", response_model=HealthResponse, tags=["System"])
def health(session: Session = Depends(get_db)) -> HealthResponse:
    """Report the state of the API, the database, the dataset and the model."""
    min_date, max_date = dataset_date_range(session)
    dataset_loaded = count_records(session) > 0
    return HealthResponse(
        status="ok" if model_service.is_loaded and dataset_loaded else "degraded",
        app=settings.app_name,
        version=settings.app_version,
        database="connected",
        dataset_loaded=dataset_loaded,
        model_loaded=model_service.is_loaded,
        network_loaded=True,
        record_count=count_records(session),
        data_notice=DATA_NOTICE
        + f" Simulated period: {min_date} to {max_date}."
        + (f" Model error: {model_service.load_error}" if model_service.load_error else ""),
        authority_auth_configured=auth_service.is_configured,
    )


# --------------------------------------------------------------------------
# Network
# --------------------------------------------------------------------------
@router.get("/network", response_model=NetworkResponse, tags=["Network"])
def get_network(session: Session = Depends(get_db)) -> NetworkResponse:
    """Return the complete (simulated) NavaCity network."""
    network = model_service.network

    metro_lines = [
        RouteSummary(
            id=line["id"],
            name=line["name"],
            mode="metro",
            color=line["color"],
            base_frequency=line["base_frequency"],
            vehicle_capacity=line["vehicle_capacity"],
            travel_minutes=line["travel_minutes"],
            popularity=line["popularity"],
            stops=line["stations"],
            stop_names=line["station_names"],
        )
        for line in network["metro_lines"]
    ]
    bus_routes = [
        RouteSummary(
            id=route["id"],
            name=route["name"],
            mode="bus",
            color=route["color"],
            base_frequency=route["base_frequency"],
            vehicle_capacity=route["vehicle_capacity"],
            travel_minutes=route["travel_minutes"],
            popularity=route["popularity"],
            stops=route["stops"],
            stop_names=route["stop_names"],
        )
        for route in network["bus_routes"]
    ]
    places = [
        PlaceSchema(
            id=place["id"],
            name=place["name"],
            kind=place["kind"],
            x=place["x"],
            y=place["y"],
            zone=place["zone"],
            is_interchange=place["is_interchange"],
            metro_lines=place["metro_lines"],
            bus_routes=place["bus_routes"],
        )
        for place in network["places"]
    ]
    return NetworkResponse(
        city=network.get("city", "NavaCity"),
        data_notice=DATA_NOTICE,
        metro_lines=metro_lines,
        bus_routes=bus_routes,
        places=places,
    )


@router.get("/routes", response_model=list[RouteSummary], tags=["Network"])
def list_routes(
    mode: str | None = Query(None, pattern="^(metro|bus)$"),
    session: Session = Depends(get_db),
) -> list[RouteSummary]:
    """List the metro lines and bus routes, optionally filtered by mode."""
    stmt = select(Route)
    if mode:
        stmt = stmt.where(Route.mode == mode)
    stmt = stmt.order_by(Route.mode, Route.id)

    network = model_service.network
    names = {line["id"]: line for line in network["metro_lines"]}
    names.update({route["id"]: route for route in network["bus_routes"]})

    result: list[RouteSummary] = []
    for route in session.execute(stmt).scalars():
        meta = names.get(route.id, {})
        result.append(
            RouteSummary(
                id=route.id,
                name=route.name,
                mode=route.mode,
                color=route.color,
                base_frequency=route.base_frequency,
                vehicle_capacity=route.vehicle_capacity,
                travel_minutes=route.travel_minutes,
                popularity=route.popularity,
                stops=meta.get("stations", meta.get("stops", [])),
                stop_names=meta.get("station_names", meta.get("stop_names", [])),
            )
        )
    return result


@router.get("/places", response_model=list[PlaceSchema], tags=["Network"])
def list_places(
    mode: str | None = Query(None, pattern="^(metro|bus)$"),
    kind: str | None = Query(None, pattern="^(station|stop)$"),
    session: Session = Depends(get_db),
) -> list[PlaceSchema]:
    """List the stations and stops, optionally filtered by mode or kind."""
    stmt = select(Place).order_by(Place.name)
    if kind:
        stmt = stmt.where(Place.kind == kind)

    places = list(session.execute(stmt).scalars())
    if mode:
        places = [
            place
            for place in places
            if (mode == "metro" and place.metro_lines)
            or (mode == "bus" and place.bus_routes)
        ]
    return [
        PlaceSchema(
            id=place.id,
            name=place.name,
            kind=place.kind,
            x=place.x,
            y=place.y,
            zone=place.zone,
            is_interchange=place.is_interchange,
            metro_lines=place.metro_lines.split(",") if place.metro_lines else [],
            bus_routes=place.bus_routes.split(",") if place.bus_routes else [],
        )
        for place in places
    ]


@router.get("/events", tags=["Network"])
def list_events() -> dict:
    """The (simulated) special events of the NavaCity calendar."""
    return {
        "data_notice": DATA_NOTICE,
        "count": len(SPECIAL_EVENTS),
        "events": [
            {
                "id": event["id"],
                "name": event["name"],
                "venue": event["venue"],
                "date": event["date"].isoformat(),
                "hour_start": event["hour_start"],
                "hour_end": event["hour_end"],
                "places": event["places"],
                "routes": event["routes"],
                "attraction": event["attraction"],
            }
            for event in SPECIAL_EVENTS
        ],
    }


@router.get("/crowd-levels", tags=["Network"])
def crowd_levels() -> dict:
    """The crowd-level thresholds and the assumptions behind them."""
    return {
        "data_notice": DATA_NOTICE,
        "levels": crowd_level_bounds(),
        "alert_threshold_pct": OVERCROWDING_ALERT_THRESHOLD * 100,
        "assumptions": [
            "Occupancy is the share of the hourly capacity offered by the "
            "planned service (vehicle capacity x service frequency).",
            "Low (0-40%): plenty of room, passengers rarely wait for a second "
            "vehicle.",
            "Moderate (40-65%): comfortable, a few passengers may wait for "
            "the next service.",
            "High (65-85%): crowded, boarding is slow and queues form.",
            "Critical (85%+): overcrowded, passengers are left behind.",
            "The 85% cut-off corresponds to roughly 0.85 m2 of space per "
            "standing passenger in a crush-loaded vehicle.",
        ],
    }


# --------------------------------------------------------------------------
# History
# --------------------------------------------------------------------------
@router.get("/history", response_model=HistoryResponse, tags=["Demand"])
def get_history(
    route_id: str | None = Query(None, description="Filter by route id"),
    mode: str | None = Query(None, pattern="^(metro|bus)$"),
    date_filter: str | None = Query(None, alias="date", description="YYYY-MM-DD"),
    hour: int | None = Query(None, ge=0, le=23),
    limit: int = Query(200, ge=1, le=2000),
    session: Session = Depends(get_db),
) -> HistoryResponse:
    """Return the SIMULATED historical demand records."""
    stmt = select(DemandRecord).order_by(
        DemandRecord.timestamp.desc(), DemandRecord.route_id
    )
    if route_id:
        stmt = stmt.where(DemandRecord.route_id == route_id.upper())
    if mode:
        stmt = stmt.where(DemandRecord.mode == mode)
    if date_filter:
        stmt = stmt.where(DemandRecord.date == date_filter)
    if hour is not None:
        stmt = stmt.where(DemandRecord.hour == hour)
    stmt = stmt.limit(min(limit, settings.max_history_rows))

    records = list(session.execute(stmt).scalars())
    records.reverse()  # oldest first, easier to plot

    return HistoryResponse(
        count=len(records),
        data_notice=DATA_NOTICE,
        records=[
            HistoryPoint(
                timestamp=record.timestamp,
                date=record.date,
                hour=record.hour,
                route_id=record.route_id,
                route_name=record.route_name,
                segment_id=record.segment_id,
                origin_name=record.origin_name,
                dest_name=record.dest_name,
                passenger_count=record.passenger_count,
                occupancy_pct=record.occupancy_pct,
                crowd_level=record.crowd_level,
                service_frequency=record.service_frequency,
                waiting_time_min=record.waiting_time_min,
                weather=record.weather,
                traffic_level=record.traffic_level,
                is_overcrowded=record.is_overcrowded,
                special_event=record.special_event,
            )
            for record in records
        ],
    )


@router.get("/history/hourly", response_model=HourlyProfileResponse, tags=["Demand"])
def get_hourly_profile(
    route_id: str | None = Query(None, description="Filter by route id"),
    mode: str | None = Query(None, pattern="^(metro|bus)$"),
    date_filter: str | None = Query(None, alias="date", description="YYYY-MM-DD"),
    session: Session = Depends(get_db),
) -> HourlyProfileResponse:
    """Mean SIMULATED demand per hour of the day (used by the charts)."""
    points = hourly_profile(session, route_id or "", date_filter, mode)
    mode_value = mode
    if mode_value is None and route_id:
        route = session.get(Route, route_id.upper())
        mode_value = route.mode if route else None
    return HourlyProfileResponse(
        route_id=route_id or "",
        mode=mode_value or "metro",
        date=date_filter or "all",
        data_notice=DATA_NOTICE,
        points=points,
    )


# --------------------------------------------------------------------------
# Prediction
# --------------------------------------------------------------------------
@router.post("/predict", response_model=PredictionResponse, tags=["Prediction"])
def predict_demand(
    payload: PredictionRequest,
    session: Session = Depends(get_db),
) -> PredictionResponse:
    """Predict the passenger demand of a route for a given day and hour."""
    if not model_service.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The demand model is not available. Run 'python ml\\train_model.py' "
                f"to build it. ({model_service.load_error})"
            ),
        )

    route_id = payload.route_id.strip().upper()
    _route_exists(session, route_id)

    if payload.mode:
        route = session.get(Route, route_id)
        if route and route.mode != payload.mode:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Route {route_id} is a {route.mode} route, not a "
                    f"{payload.mode} route."
                ),
            )

    on_date = payload.date or _next_forecast_date()
    try:
        result = model_service.predict(
            route_id=route_id,
            hour=payload.hour,
            on_date=on_date,
            segment_id=payload.segment_id,
            weather=payload.weather,
            traffic_level=payload.traffic_level,
            special_event=payload.special_event,
            origin_id=payload.origin_id,
            destination_id=payload.destination_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown route segment: {exc.args[0]}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return PredictionResponse(**_with_date_context(result, on_date))


@router.get("/predict", response_model=PredictionResponse, tags=["Prediction"])
def predict_demand_get(
    route_id: str = Query(..., description="Metro line (M1-M6) or bus route (B01-B18)"),
    hour: int = Query(..., ge=0, le=23),
    date_filter: str | None = Query(None, alias="date", description="YYYY-MM-DD"),
    segment_id: str | None = Query(None),
    origin_id: str | None = Query(None, description="Origin station / stop id"),
    destination_id: str | None = Query(None, description="Destination station / stop id"),
    session: Session = Depends(get_db),
) -> PredictionResponse:
    """Query-parameter variant of ``POST /predict`` (handy for links)."""
    if not model_service.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The demand model is not available. Run 'python ml\\train_model.py'.",
        )
    route_id = route_id.strip().upper()
    _route_exists(session, route_id)
    on_date = date.fromisoformat(date_filter) if date_filter else _next_forecast_date()
    try:
        result = model_service.predict(
            route_id=route_id,
            hour=hour,
            on_date=on_date,
            segment_id=segment_id,
            origin_id=origin_id,
            destination_id=destination_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown route segment: {exc.args[0]}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return PredictionResponse(**_with_date_context(result, on_date))


@router.get("/predict/day", tags=["Prediction"])
def predict_day(
    route_id: str = Query(..., description="Metro line (M1-M6) or bus route (B01-B18)"),
    date_filter: str | None = Query(None, alias="date", description="YYYY-MM-DD"),
    segment_id: str | None = Query(None),
    origin_id: str | None = Query(None, description="Origin station / stop id"),
    destination_id: str | None = Query(None, description="Destination station / stop id"),
    session: Session = Depends(get_db),
) -> dict:
    """Predict all 24 hours of a route for the given day (chart data)."""
    if not model_service.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The demand model is not available. Run 'python ml\\train_model.py'.",
        )
    route_id = route_id.strip().upper()
    _route_exists(session, route_id)
    on_date = date.fromisoformat(date_filter) if date_filter else _next_forecast_date()
    try:
        predictions = model_service.predict_batch(
            route_id=route_id, hours=list(range(24)), on_date=on_date,
            segment_id=segment_id,
            origin_id=origin_id,
            destination_id=destination_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown route segment: {exc.args[0]}",
        ) from exc
    notice = _extrapolation_notice(on_date)
    return {
        "route_id": route_id,
        "date": on_date.isoformat(),
        "data_notice": DATA_NOTICE,
        "is_extrapolation": notice is not None,
        "extrapolation_notice": notice,
        "supported_date_range": _supported_date_range(),
        "predictions": predictions,
    }


# --------------------------------------------------------------------------
# Crowd level summary and alerts
#
# These two endpoints aggregate the whole simulated history and are used by
# the transport-authority dashboard, so they are protected as well.
# --------------------------------------------------------------------------
@router.get(
    "/crowd-summary",
    response_model=CrowdSummaryResponse,
    tags=["Authority"],
    dependencies=[Depends(require_authority)],
)
def get_crowd_summary(
    mode: str | None = Query(None, pattern="^(metro|bus)$"),
    route_id: str | None = Query(None),
    session: Session = Depends(get_db),
) -> CrowdSummaryResponse:
    """Distribution of the SIMULATED crowd levels (authority only)."""
    if route_id:
        _route_exists(session, route_id.upper())
    return crowd_summary(session, mode, route_id.upper() if route_id else None)


@router.get(
    "/alerts",
    response_model=AlertsResponse,
    tags=["Authority"],
    dependencies=[Depends(require_authority)],
)
def get_alerts(
    mode: str | None = Query(None, pattern="^(metro|bus)$"),
    date_filter: str | None = Query(None, alias="date", description="YYYY-MM-DD"),
    threshold: float = Query(
        OVERCROWDING_ALERT_THRESHOLD, ge=0.0, le=2.0,
        description="Occupancy ratio above which an alert is raised",
    ),
    limit: int = Query(50, ge=1, le=500),
    session: Session = Depends(get_db),
) -> AlertsResponse:
    """Route segments and hours whose SIMULATED occupancy is critical."""
    alerts = overcrowding_alerts(
        session, mode=mode, date_filter=date_filter, threshold=threshold, limit=limit
    )
    return AlertsResponse(
        count=len(alerts),
        threshold_pct=round(threshold * 100.0, 2),
        data_notice=DATA_NOTICE,
        alerts=alerts,
    )


# --------------------------------------------------------------------------
# Authority dashboard
# --------------------------------------------------------------------------
@router.get(
    "/authority/stats",
    response_model=AuthorityStatsResponse,
    tags=["Authority"],
    dependencies=[Depends(require_authority)],
)
def get_authority_stats(
    date_filter: str | None = Query(None, alias="date", description="YYYY-MM-DD"),
    mode: str | None = Query(None, pattern="^(metro|bus)$"),
    session: Session = Depends(get_db),
) -> AuthorityStatsResponse:
    """KPI cards, bus vs metro comparison, route analytics and recommendations.

    The optional ``mode`` parameter restricts the whole payload to one
    transport mode, so the Metro and the Bus tab of the authority dashboard
    are served by the same endpoint.
    """
    return authority_stats(session, date_filter, mode)


@router.get(
    "/authority/recommendations",
    tags=["Authority"],
    dependencies=[Depends(require_authority)],
)
def get_recommendations(
    limit: int = Query(20, ge=1, le=100),
    mode: str | None = Query(None, pattern="^(metro|bus)$"),
    session: Session = Depends(get_db),
) -> dict:
    """Suggested service-frequency changes (recommendations, not decisions)."""
    from .services.analytics_service import (
        RECOMMENDATION_DISCLAIMER,
        service_recommendations,
    )

    recommendations = service_recommendations(session, limit=limit, mode=mode)
    return {
        "count": len(recommendations),
        "mode": mode,
        "data_notice": DATA_NOTICE,
        "disclaimer": RECOMMENDATION_DISCLAIMER,
        "recommendations": [item.model_dump() for item in recommendations],
    }


@router.get(
    "/authority/mode-summary",
    tags=["Authority"],
    dependencies=[Depends(require_authority)],
)
def get_mode_summary(
    session: Session = Depends(get_db),
) -> dict:
    """A side-by-side summary of the two transport modes.

    The comparison uses the metrics that are actually comparable between a
    320-seat metro vehicle and a 48-seat bus: the mean occupancy and the
    passengers per vehicle.  The absolute passenger totals are included as
    secondary information only.
    """
    from .services.analytics_service import mode_comparison, route_analytics

    comparisons = mode_comparison(session)
    busiest: dict[str, str] = {}
    for mode in ("metro", "bus"):
        rows = route_analytics(session, mode)
        busiest[mode] = rows[0].route_id if rows else ""
    return {
        "data_notice": DATA_NOTICE,
        "comparison": [item.model_dump() for item in comparisons],
        "busiest_route": busiest,
    }


# --------------------------------------------------------------------------
# Alternatives
# --------------------------------------------------------------------------
@router.get("/alternatives", response_model=AlternativesResponse, tags=["Public"])
def get_alternatives(
    route_id: str = Query(..., description="The route the traveller wants to use"),
    origin_id: str = Query(..., description="Origin station / stop id"),
    destination_id: str = Query(..., description="Destination station / stop id"),
    hour: int = Query(8, ge=0, le=23),
    date_filter: str | None = Query(None, alias="date", description="YYYY-MM-DD"),
    limit: int = Query(5, ge=1, le=20),
    session: Session = Depends(get_db),
) -> AlternativesResponse:
    """Suggest less crowded alternative routes for the same journey."""
    if not model_service.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The demand model is not available. Run 'python ml\\train_model.py'.",
        )
    route_id = route_id.strip().upper()
    _route_exists(session, route_id)

    index = model_service.index
    if origin_id not in index["places"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown origin place id: {origin_id}",
        )
    if destination_id not in index["places"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown destination place id: {destination_id}",
        )

    on_date = date.fromisoformat(date_filter) if date_filter else _next_forecast_date()
    try:
        return suggest_alternatives(
            route_id=route_id,
            origin_id=origin_id,
            destination_id=destination_id,
            hour=hour,
            on_date=on_date,
            max_results=limit,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown route: {exc.args[0]}",
        ) from exc


# --------------------------------------------------------------------------
# Model metrics
#
# The evaluation metrics are part of the authority reporting, so they are
# protected.  The frontend shows them only after a successful sign-in.
# --------------------------------------------------------------------------
@router.get(
    "/model/metrics",
    response_model=ModelMetricsResponse,
    tags=["Model"],
    dependencies=[Depends(require_authority)],
)
def get_model_metrics() -> ModelMetricsResponse:
    """The evaluation metrics produced by ``ml/train_model.py``."""
    metrics = model_service.metrics
    if not metrics:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "No metrics found. Run 'python ml\\train_model.py' to train the "
                "model and produce the metrics file."
            ),
        )
    return ModelMetricsResponse(
        data_notice=metrics.get(
            "data_notice", "SIMULATED DATA - metrics measured on simulated data."
        ),
        dataset=metrics.get("dataset", {}),
        split=metrics.get("split", {}),
        modes=metrics.get("modes", {}),
        mean_feature_importance=metrics.get("mean_feature_importance", {}),
        crowd_thresholds=metrics.get("crowd_thresholds", []),
    )


# --------------------------------------------------------------------------
# Date-range helpers
#
# The model was trained on the simulated window.  A request for a day outside
# that window is still answered (the API is a forecast), but the answer says
# explicitly that it is an extrapolation.
# --------------------------------------------------------------------------
def _supported_date_range() -> dict:
    """The window the model was trained on, as a JSON-serialisable dict."""
    return {
        "start": SIM_START_DATE.isoformat(),
        "end": SIM_END_DATE.isoformat(),
        "observed_months": sorted(OBSERVED_MONTHS),
    }


def _extrapolation_notice(on_date: date) -> str | None:
    """Explain why a forecast for ``on_date`` is an extrapolation."""
    if not is_within_simulated_window(on_date):
        return (
            f"{on_date.isoformat()} is outside the simulated period "
            f"({SIM_START_DATE.isoformat()} to {SIM_END_DATE.isoformat()}). "
            "This forecast is an extrapolation: the model has not seen this "
            "part of the calendar."
        )
    if not is_within_observed_months(on_date):
        return (
            f"The simulated data only covers months "
            f"{', '.join(str(m) for m in sorted(OBSERVED_MONTHS))}, so the "
            "monthly pattern of the forecast for "
            f"{on_date.isoformat()} is an extrapolation."
        )
    return None


def _with_date_context(result: dict, on_date: date) -> dict:
    """Add the extrapolation metadata to a prediction payload."""
    notice = _extrapolation_notice(on_date)
    enriched = dict(result)
    enriched["is_extrapolation"] = notice is not None
    enriched["extrapolation_notice"] = notice
    enriched["supported_date_range"] = _supported_date_range()
    return enriched
