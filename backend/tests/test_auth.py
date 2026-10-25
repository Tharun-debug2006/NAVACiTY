"""Tests of the backend-enforced authority authentication.

The authority area must be protected **by the server**, not by the React
app: a request without a valid session token has to be rejected with a
``401`` no matter which client sends it.

These tests cover

* the login / logout round trip,
* the rejection of a wrong password,
* the protection of every authority-only endpoint,
* the fact that the public endpoints stay reachable without credentials,
* the expiry of a session,
* the production configuration validation.
"""

from __future__ import annotations

import time

import pytest

from backend.app.auth import auth_service
from backend.app.config import settings
from backend.app.main import app, validate_startup_configuration
from backend.app.security import (
    SessionPayload,
    decode_token,
    hash_password,
    issue_token,
    verify_password,
)

#: The endpoints that must never answer without a session token.
PROTECTED_ENDPOINTS = [
    "/api/authority/stats",
    "/api/authority/recommendations",
    "/api/crowd-summary",
    "/api/alerts",
    "/api/model/metrics",
]

#: The endpoints that must stay open for the public dashboard.  The value is
#: the path *with* the query parameters the endpoint needs, so that a bare
#: request does not fail with a 422 (which would not say anything about the
#: authentication).
PUBLIC_ENDPOINTS = [
    "/api/health",
    "/api/network",
    "/api/routes",
    "/api/places",
    "/api/events",
    "/api/crowd-levels",
    "/api/history?limit=5",
    "/api/history/hourly?route_id=M1",
    "/api/predict/day?route_id=M1",
]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def login(client, password: str = "dumpme") -> str:
    """Sign in and return the session token."""
    response = client.post("/api/auth/login", json={"password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------
# The password verifier
# --------------------------------------------------------------------------
def test_password_hash_round_trip():
    salt, digest = hash_password("s3cret-pass")
    assert verify_password("s3cret-pass", salt, digest)
    assert not verify_password("wrong-pass", salt, digest)
    assert not verify_password("s3cret-pass", salt, digest[:-2] + "00")


def test_password_hash_uses_a_random_salt():
    salt_a, digest_a = hash_password("same")
    salt_b, digest_b = hash_password("same")
    assert salt_a != salt_b
    assert digest_a != digest_b


# --------------------------------------------------------------------------
# The session token
# --------------------------------------------------------------------------
def test_token_round_trip():
    payload = SessionPayload(
        session_id="abc", issued_at=int(time.time()), expires_at=int(time.time()) + 60
    )
    token = issue_token(payload, "secret")
    decoded = decode_token(token, "secret")
    assert decoded is not None
    assert decoded.session_id == "abc"


def test_token_signed_with_another_secret_is_rejected():
    payload = SessionPayload(
        session_id="abc", issued_at=int(time.time()), expires_at=int(time.time()) + 60
    )
    token = issue_token(payload, "secret")
    assert decode_token(token, "other-secret") is None


def test_tampered_token_is_rejected():
    payload = SessionPayload(
        session_id="abc", issued_at=int(time.time()), expires_at=int(time.time()) + 60
    )
    token = issue_token(payload, "secret")
    body, _, signature = token.partition(".")
    assert decode_token(f"{body}x.{signature}", "secret") is None


def test_expired_token_is_rejected():
    payload = SessionPayload(
        session_id="abc", issued_at=int(time.time()) - 120, expires_at=int(time.time()) - 60
    )
    token = issue_token(payload, "secret")
    assert decode_token(token, "secret") is None


def test_garbage_token_is_rejected():
    assert decode_token("not-a-token", "secret") is None
    assert decode_token("", "secret") is None
    assert decode_token("a.b.c", "secret") is None



# --------------------------------------------------------------------------
# The login endpoint
# --------------------------------------------------------------------------
def test_login_succeeds_with_the_configured_password(client):
    response = client.post("/api/auth/login", json={"password": "dumpme"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["expires_at"] > payload["session"]["issued_at"]
    assert payload["session"]["role"] == "authority"


def test_login_rejects_a_wrong_password(client):
    response = client.post("/api/auth/login", json={"password": "not-the-password"})
    assert response.status_code == 401
    assert "password" in response.json()["detail"].lower()


def test_login_rejects_an_empty_password(client):
    response = client.post("/api/auth/login", json={"password": ""})
    assert response.status_code == 422


def test_login_rejects_a_missing_password(client):
    response = client.post("/api/auth/login", json={})
    assert response.status_code == 422


def test_login_does_not_leak_the_password_in_the_response(client):
    response = client.post("/api/auth/login", json={"password": "dumpme"})
    assert "dumpme" not in response.text


# --------------------------------------------------------------------------
# The protected endpoints
# --------------------------------------------------------------------------
@pytest.mark.parametrize("path", PROTECTED_ENDPOINTS)
def test_authority_endpoints_require_a_token(client, path):
    response = client.get(path)
    assert response.status_code == 401, f"{path} was not protected"
    assert "WWW-Authenticate" in response.headers


@pytest.mark.parametrize("path", PROTECTED_ENDPOINTS)
def test_authority_endpoints_reject_a_forged_token(client, path):
    response = client.get(path, headers=auth_header("forged.token.value"))
    assert response.status_code == 401, f"{path} accepted a forged token"


@pytest.mark.parametrize("path", PROTECTED_ENDPOINTS)
def test_authority_endpoints_accept_a_valid_token(client, path):
    token = login(client)
    response = client.get(path, headers=auth_header(token))
    assert response.status_code == 200, f"{path} rejected a valid token: {response.text[:200]}"


@pytest.mark.parametrize("path", PUBLIC_ENDPOINTS)
def test_public_endpoints_stay_open(client, path):
    response = client.get(path)
    assert response.status_code == 200, f"{path} is not public any more"


def test_the_public_prediction_endpoint_stays_open(client):
    response = client.post(
        "/api/predict", json={"route_id": "M1", "hour": 8, "date": "2025-06-30"}
    )
    assert response.status_code == 200


def test_the_alternatives_endpoint_stays_open(client):
    response = client.get(
        "/api/alternatives?route_id=M1"
        "&origin_id=ST-navacitycentral"
        "&destination_id=ST-whitefielddepot&hour=8"
    )
    assert response.status_code == 200



# --------------------------------------------------------------------------
# The session lifecycle
# --------------------------------------------------------------------------
def test_session_endpoint_reports_the_current_session(client):
    token = login(client)
    response = client.get("/api/auth/session", headers=auth_header(token))
    assert response.status_code == 200
    assert response.json()["role"] == "authority"


def test_logout_invalidates_the_token_immediately(client):
    token = login(client)
    assert client.get("/api/authority/stats", headers=auth_header(token)).status_code == 200

    logout = client.post("/api/auth/logout", headers=auth_header(token))
    assert logout.status_code == 200
    assert logout.json()["revoked"] is True

    # The very same token must not work any more.
    after = client.get("/api/authority/stats", headers=auth_header(token))
    assert after.status_code == 401


def test_logout_requires_a_token(client):
    assert client.post("/api/auth/logout").status_code == 401


def test_an_expired_session_is_rejected(client):
    """A session whose expiry has passed must not be accepted any more."""
    token = login(client)
    payload = auth_service.validate_token(token)
    assert payload is not None

    # Move the expiry of the live session into the past.
    session = auth_service._sessions[payload.session_id]
    session.expires_at = int(time.time()) - 1

    response = client.get("/api/authority/stats", headers=auth_header(token))
    assert response.status_code == 401


def test_two_logins_create_two_independent_sessions(client):
    first = login(client)
    second = login(client)
    assert first != second
    assert client.get(
        "/api/authority/stats", headers=auth_header(first)
    ).status_code == 200
    assert client.get(
        "/api/authority/stats", headers=auth_header(second)
    ).status_code == 200


def test_logging_out_does_not_invalidate_the_other_session(client):
    first = login(client)
    second = login(client)
    client.post("/api/auth/logout", headers=auth_header(first))
    assert client.get(
        "/api/authority/stats", headers=auth_header(second)
    ).status_code == 200


# --------------------------------------------------------------------------
# The configuration endpoint
# --------------------------------------------------------------------------
def test_auth_config_is_public_and_hides_the_secret(client):
    response = client.get("/api/auth/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert payload["session_minutes"] > 0
    assert "dumpme" not in response.text


def payload_is_password_free(payload: dict) -> bool:
    """True when no value of the payload contains the demo password."""
    return all("dumpme" not in str(value) for value in payload.values())


def test_auth_config_never_echoes_the_configured_password(monkeypatch, client):
    """The public config endpoint must not disclose *any* password.

    The demo password is a well-known constant, but a real deployment must
    not leak its configured password through a public response either.
    """
    secret = "a-very-secret-production-password"
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "auth_password", secret)
    monkeypatch.setattr(settings, "auth_password_hash", "")
    auth_service.configure()
    try:
        response = client.get("/api/auth/config")
        assert response.status_code == 200
        assert secret not in response.text
        assert payload_is_password_free(response.json())
    finally:
        monkeypatch.setattr(settings, "environment", "local")
        monkeypatch.setattr(settings, "auth_password", "dumpme")
        auth_service.configure()


def test_the_demo_password_is_refused_in_the_public_config(monkeypatch, client):
    """The production refusal message must not quote the password."""
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "auth_password", "dumpme")
    monkeypatch.setattr(settings, "auth_password_hash", "")
    auth_service.configure()
    try:
        response = client.get("/api/auth/config")
        assert response.status_code == 200
        assert "dumpme" not in response.text
    finally:
        monkeypatch.setattr(settings, "environment", "local")
        monkeypatch.setattr(settings, "auth_password", "dumpme")
        auth_service.configure()


def test_health_reports_the_authentication_state(client):
    payload = client.get("/api/health").json()
    assert payload["authority_auth_configured"] is True



# --------------------------------------------------------------------------
# The production configuration
# --------------------------------------------------------------------------
def test_production_refuses_to_start_without_a_password(monkeypatch):
    """A production server must not start without a secure password."""
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "auth_password", "")
    monkeypatch.setattr(settings, "auth_password_hash", "")
    with pytest.raises(RuntimeError) as excinfo:
        validate_startup_configuration()
    assert "REFUSING TO START" in str(excinfo.value)


def test_production_refuses_the_demo_password(monkeypatch):
    """The demo password 'dumpme' must not be accepted in production."""
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "auth_password", "dumpme")
    monkeypatch.setattr(settings, "auth_password_hash", "")
    with pytest.raises(RuntimeError) as excinfo:
        validate_startup_configuration()
    assert "REFUSING TO START" in str(excinfo.value)


def test_production_starts_with_a_secure_password(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "auth_password", "a-strong-password")
    monkeypatch.setattr(settings, "auth_password_hash", "")
    # Must not raise.
    validate_startup_configuration()
    assert auth_service.is_configured
    assert auth_service.is_demo_mode is False


def test_local_mode_allows_the_demo_password(monkeypatch):
    monkeypatch.setattr(settings, "environment", "local")
    monkeypatch.setattr(settings, "auth_password", "dumpme")
    monkeypatch.setattr(settings, "auth_password_hash", "")
    validate_startup_configuration()
    assert auth_service.is_configured
    assert auth_service.is_demo_mode is True
    assert auth_service.check_password("dumpme")
    assert not auth_service.check_password("something-else")


def test_the_demo_password_is_refused_in_production_mode(monkeypatch):
    """Even when the service is configured directly, 'dumpme' must fail."""
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "auth_password", "dumpme")
    monkeypatch.setattr(settings, "auth_password_hash", "")
    auth_service.configure()
    assert not auth_service.is_configured
    assert not auth_service.check_password("dumpme")
    # Restore the demo configuration for the remaining tests.
    monkeypatch.setattr(settings, "environment", "local")
    auth_service.configure()


def test_a_configured_password_is_required_for_a_login(client, monkeypatch):
    """Without a configured password the login endpoint answers 503."""
    monkeypatch.setattr(settings, "auth_password", "")
    monkeypatch.setattr(settings, "auth_password_hash", "")
    auth_service.configure()
    try:
        response = client.post("/api/auth/login", json={"password": "anything"})
        assert response.status_code == 503
    finally:
        monkeypatch.setattr(settings, "auth_password", "dumpme")
        auth_service.configure()
