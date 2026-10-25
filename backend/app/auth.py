"""Backend-enforced authentication for the transport-authority area.

The authority endpoints (``/api/authority/*`` and the authority-only
statistics) are protected by this module.  The protection is enforced by
FastAPI itself, so it does not matter whether the caller is the React app, a
``curl`` command or a script: without a valid session token the server
answers ``401 Unauthorized``.

Configuration
-------------
``NAVACITY_AUTH_PASSWORD``
    The password of the transport authority.  Required.

``NAVACITY_ENV``
    ``local`` (default) or ``production``.

    * ``local`` allows the demo password ``dumpme`` so that the project can be
      started without any setup.  The API reports the demo mode in
      ``/api/auth/config`` and in the login response.
    * ``production`` **refuses** the demo password and refuses to start
      without a configured password.

``NAVACITY_AUTH_SESSION_MINUTES``
    Lifetime of a session token in minutes (default 60).

``NAVACITY_AUTH_SECRET``
    The HMAC secret used to sign the session tokens.  When it is not set a
    random secret is generated at start-up, which means that restarting the
    server invalidates all existing sessions (the desired behaviour for a
    single-process demo).

``NAVACITY_AUTH_PASSWORD_HASH``
    Optional ``salt_hex:hash_hex`` pair, so the password can be supplied as a
    PBKDF2 hash instead of in plain text.
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings
from .security import (
    DEMO_PASSWORD,
    SessionPayload,
    decode_token,
    hash_password,
    issue_token,
    verify_password,
)

# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------
AUTHENTICATION_ERROR = "Not authenticated. Sign in to the authority dashboard."


def _unauthorized(detail: str = AUTHENTICATION_ERROR) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )



# --------------------------------------------------------------------------
# Session registry
# --------------------------------------------------------------------------
@dataclass
class Session:
    """A live authority session."""

    session_id: str
    issued_at: int
    expires_at: int


class AuthService:
    """Holds the credential verifier and the live session registry."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, Session] = {}
        self._secret = settings.auth_secret or secrets.token_urlsafe(48)
        self._salt: str | None = None
        self._hash: str | None = None
        self._demo_mode = False
        self._configured = False
        self._error: str | None = None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def configure(self) -> None:
        """Resolve the credential from the environment.

        Called once at start-up.  It never raises: an invalid configuration
        is recorded in :attr:`error` and turned into a ``503`` by the
        endpoints, so that the public part of the API keeps working.
        """
        with self._lock:
            self._sessions.clear()
            self._configured = False
            self._demo_mode = False
            self._error = None
            self._salt = None
            self._hash = None

            raw_hash = settings.auth_password_hash.strip()
            raw_password = settings.auth_password

            if raw_hash:
                if ":" not in raw_hash:
                    self._error = (
                        "NAVACITY_AUTH_PASSWORD_HASH must have the format "
                        "'salt_hex:hash_hex'."
                    )
                    return
                salt_hex, _, hash_hex = raw_hash.partition(":")
                self._salt = salt_hex
                self._hash = hash_hex
                self._configured = True
                return

            if not raw_password:
                self._error = (
                    "No authority password is configured. Set "
                    "NAVACITY_AUTH_PASSWORD (or NAVACITY_AUTH_PASSWORD_HASH) "
                    "before starting the server."
                )
                return

            if raw_password == DEMO_PASSWORD:
                if settings.environment != "local":
                    # The message is returned by the *public* /auth/config
                    # endpoint, so it must not repeat the credential itself.
                    self._error = (
                        "The well-known local demo password is only allowed "
                        "when NAVACITY_ENV=local. Set NAVACITY_ENV=production "
                        "and configure a real NAVACITY_AUTH_PASSWORD."
                    )
                    return
                self._demo_mode = True
                self._configured = True
                return

            salt, digest = hash_password(raw_password)
            self._salt = salt
            self._hash = digest
            self._configured = True

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    @property
    def is_configured(self) -> bool:
        return self._configured and self._error is None

    @property
    def is_demo_mode(self) -> bool:
        return self._demo_mode

    @property
    def error(self) -> str | None:
        return self._error

    @property
    def environment(self) -> str:
        return settings.environment

    @property
    def session_minutes(self) -> int:
        return settings.auth_session_minutes

    def describe(self) -> dict:
        """A payload the login screen can use to explain the current setup."""
        return {
            "environment": self.environment,
            "demo_mode": self.is_demo_mode,
            "configured": self.is_configured,
            "session_minutes": self.session_minutes,
            "error": self.error,
        }

    # ------------------------------------------------------------------
    # Credentials
    # ------------------------------------------------------------------
    def check_password(self, password: str) -> bool:
        """Verify a password.  Returns False when no password is configured."""
        if not self._configured or self._error:
            return False
        if self._demo_mode:
            return secrets.compare_digest(
                (password or "").encode("utf-8"), DEMO_PASSWORD.encode("utf-8")
            )
        if self._salt is None or self._hash is None:
            return False
        return verify_password(password, self._salt, self._hash)

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------
    def create_session(self) -> tuple[str, SessionPayload]:
        """Create a new session and return ``(token, payload)``."""
        now = int(time.time())
        expires_at = now + self.session_minutes * 60
        session_id = secrets.token_urlsafe(24)
        payload = SessionPayload(
            session_id=session_id, issued_at=now, expires_at=expires_at
        )
        token = issue_token(payload, self._secret)
        with self._lock:
            self._sessions[session_id] = Session(
                session_id=session_id, issued_at=now, expires_at=expires_at
            )
        return token, payload

    def validate_token(self, token: str | None) -> SessionPayload | None:
        """Return the payload of a valid, non-revoked session token."""
        if not token:
            return None
        payload = decode_token(token, self._secret)
        if payload is None:
            return None
        with self._lock:
            session = self._sessions.get(payload.session_id)
            if session is None:
                # The session was revoked (logout) or the server restarted
                # with a freshly generated secret.
                return None
            if session.expires_at <= int(time.time()):
                self._sessions.pop(payload.session_id, None)
                return None
        return payload

    def revoke_session(self, session_id: str) -> bool:
        """Invalidate one session.  Returns True when a session was removed."""
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def revoke_all(self) -> int:
        """Invalidate every session (used when the password changes)."""
        with self._lock:
            count = len(self._sessions)
            self._sessions.clear()
            return count

    def active_session_count(self) -> int:
        """The number of sessions that have not expired yet."""
        with self._lock:
            now = int(time.time())
            return sum(1 for s in self._sessions.values() if s.expires_at > now)


# --------------------------------------------------------------------------
# Singleton + FastAPI dependencies
# --------------------------------------------------------------------------
auth_service = AuthService()

bearer_scheme = HTTPBearer(auto_error=False, description="Authority session token")


def get_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str | None:
    """Extract the bearer token from the ``Authorization`` header."""
    if credentials is None:
        return None
    if (credentials.scheme or "").lower() != "bearer":
        return None
    return credentials.credentials


def require_authority(
    token: str | None = Depends(get_bearer_token),
) -> SessionPayload:
    """FastAPI dependency that enforces authority authentication.

    Raises ``401`` when the token is missing, invalid, expired or revoked.
    """
    if not auth_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Authority authentication is not configured: "
                f"{auth_service.error}"
            ),
        )
    payload = auth_service.validate_token(token)
    if payload is None:
        raise _unauthorized()
    return payload


def optional_authority(
    token: str | None = Depends(get_bearer_token),
) -> SessionPayload | None:
    """Return the session payload when a valid token is present, else None."""
    if not auth_service.is_configured:
        return None
    return auth_service.validate_token(token)


def client_ip(request: Request) -> str:
    """Best-effort client address (used for the audit log of the logins)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


auth_service.configure()
