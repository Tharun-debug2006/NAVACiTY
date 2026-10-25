"""Application settings for the NavaCity backend.

Everything has a sensible default so the project runs without any
environment variable.  Only the database path and the CORS origins are worth
overriding in a real deployment.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration (override with NAVACITY_* environment variables)."""

    model_config = SettingsConfigDict(
        env_prefix="NAVACITY_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "NavaCity Smart Transport API"
    app_version: str = "1.0.0"

    db_path: Path = REPO_ROOT / "data" / "navacity.db"
    dataset_csv: Path = REPO_ROOT / "data" / "generated" / "navacity_transport.csv"
    network_json: Path = REPO_ROOT / "data" / "generated" / "navacity_network.json"
    model_bundle: Path = REPO_ROOT / "ml" / "artifacts" / "model_bundle.joblib"
    metrics_json: Path = REPO_ROOT / "ml" / "artifacts" / "metrics.json"

    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:4173,http://127.0.0.1:4173"
    )

    # Number of simulated historical rows returned per query (keeps the
    # payload small and the charts fast).
    max_history_rows: int = 500

    # ------------------------------------------------------------------
    # Authority authentication
    # ------------------------------------------------------------------
    # "local" allows the demo password "dumpme"; "production" refuses it and
    # refuses to start without a configured password.
    environment: str = "local"

    # The password of the transport authority.  Never stored: only a PBKDF2
    # hash of it is kept in memory.
    auth_password: str = "dumpme"

    # Optional "salt_hex:hash_hex" pair, used instead of auth_password.
    auth_password_hash: str = ""

    # HMAC secret used to sign the session tokens.  A random one is generated
    # when this is empty (so restarting the server invalidates all sessions).
    auth_secret: str = ""

    # Lifetime of an authority session, in minutes.
    auth_session_minutes: int = 60

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"


settings = Settings()
