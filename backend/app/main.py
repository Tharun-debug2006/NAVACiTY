"""NavaCity Smart Transport API - FastAPI application entry point.

Run it from the repository root with::

    python -m uvicorn backend.app.main:app --reload --port 8000

The interactive API documentation is served at http://localhost:8000/docs
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Make the repository root importable so that `navacity_core` and `backend`
# can be imported no matter where uvicorn is started from.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from .api import router  # noqa: E402
from .auth import auth_service  # noqa: E402
from .config import settings  # noqa: E402
from .database import Base, engine  # noqa: E402
from .services.model_service import model_service  # noqa: E402

DESCRIPTION = """
NavaCity Smart Transport API

**All data served by this API is SIMULATED.** NavaCity is a fictional city;
the passenger figures come from a rule-based simulator and the forecasts come
from a scikit-learn model trained on that simulated data. Nothing here
describes a real transit operator.

### Groups
* **System** - health check
* **Network** - routes, stations, stops, events and the crowd-level rules
* **Demand** - simulated history
* **Prediction** - demand forecasts for a route, day and hour
* **Public** - alternative (less crowded) route suggestions
* **Authority** - sign-in and the authority-only statistics, alerts,
  recommendations and model evaluation
* **Model** - the evaluation metrics of the trained models

### Authentication
The authority endpoints (`/api/authority/*`, `/api/alerts`,
`/api/crowd-summary` and `/api/model/metrics`) require a session token.
Call `POST /api/auth/login` with the transport-authority password to obtain
one, then send it as `Authorization: Bearer <token>`. The public endpoints
stay open without any credentials.
"""

#: The error raised when the server is started in production mode without a
#: properly configured authority password.
PRODUCTION_AUTH_ERROR = (
    "REFUSING TO START: NAVACITY_ENV=production requires a secure authority "
    "password.\n"
    "  * Set NAVACITY_AUTH_PASSWORD to a strong, unique password, or\n"
    "  * Set NAVACITY_AUTH_PASSWORD_HASH to a 'salt_hex:hash_hex' pair.\n"
    "The demo password 'dumpme' is only accepted when NAVACITY_ENV=local."
)


def validate_startup_configuration() -> None:
    """Refuse to start a production server without a secure password.

    In ``local`` mode a missing password only produces a warning, so the
    public part of the API stays usable for the demo.  In ``production``
    mode the process is stopped, because an unprotected authority area would
    expose the statistics and the recommendations to anybody.
    """
    auth_service.configure()

    if settings.is_production:
        if not auth_service.is_configured:
            raise RuntimeError(
                f"{PRODUCTION_AUTH_ERROR}\nReason: {auth_service.error}"
            )
        if auth_service.is_demo_mode:
            raise RuntimeError(
                f"{PRODUCTION_AUTH_ERROR}\n"
                "Reason: the configured password is the demo password."
            )
        print(
            "[NavaCity] production mode: authority authentication is enabled.",
            file=sys.stderr,
        )
        return

    if not auth_service.is_configured:
        print(
            "[NavaCity] WARNING: authority authentication is not configured "
            f"({auth_service.error}). The authority endpoints will answer "
            "503 until NAVACITY_AUTH_PASSWORD is set.",
            file=sys.stderr,
        )
    elif auth_service.is_demo_mode:
        print(
            "[NavaCity] local demo mode: the authority password is 'dumpme'. "
            "Never run the server this way in a real deployment.",
            file=sys.stderr,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the tables and load the model bundle on start-up."""
    Base.metadata.create_all(bind=engine)
    validate_startup_configuration()
    loaded = model_service.load()
    if not loaded:
        print(
            "[NavaCity] WARNING: the demand model could not be loaded "
            f"({model_service.load_error}). "
            "Run 'python ml\\train_model.py' to build it.",
            file=sys.stderr,
        )
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/", tags=["System"])
def root() -> dict:
    """Small landing payload with the most useful links."""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "data_notice": (
            "SIMULATED DATA - NavaCity is a fictional city. All figures are "
            "simulated and must not be used for real operational decisions."
        ),
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json",
        },
        "authentication": {
            "note": (
                "The authority endpoints require a session token. Call "
                "POST /api/auth/login to obtain one."
            ),
            "login": "/api/auth/login",
            "logout": "/api/auth/logout",
            "session": "/api/auth/session",
            "config": "/api/auth/config",
        },
        "endpoints": [
            "/api/health",
            "/api/network",
            "/api/routes",
            "/api/places",
            "/api/events",
            "/api/crowd-levels",
            "/api/history",
            "/api/history/hourly",
            "/api/predict",
            "/api/predict/day",
            "/api/alternatives",
            "/api/auth/config",
            "/api/auth/login",
            "/api/auth/logout",
            "/api/auth/session",
            "/api/authority/stats",
            "/api/authority/recommendations",
            "/api/crowd-summary",
            "/api/alerts",
            "/api/model/metrics",
        ],
    }
