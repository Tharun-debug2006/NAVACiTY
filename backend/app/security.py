"""Password hashing and session-token helpers for the authority area.

Everything here uses the Python standard library only (``hashlib``,
``hmac``, ``secrets``, ``base64``).  The project deliberately avoids extra
native dependencies (bcrypt / passlib), so the password verifier is built on
PBKDF2-HMAC-SHA256, which is a standard, salted key-derivation function.

Design notes
------------
* The password is **never** stored.  Only a salt and a PBKDF2 hash of the
  configured password are kept, and the salt is generated per process when no
  explicit ``NAVACITY_AUTH_PASSWORD_HASH`` is configured.
* The comparison is done with :func:`hmac.compare_digest`, so it is not
  vulnerable to a timing side channel.
* Session tokens are ``base64url(payload).base64url(signature)`` where the
  signature is an HMAC-SHA256 over the payload using the server secret.  The
  payload carries the session id, the issue time and the expiry time.
* The session id is additionally kept in a server-side registry so that a
  logout (or a password rotation) can invalidate a token immediately instead
  of waiting for it to expire.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

# Number of PBKDF2 iterations.  High enough to make an offline brute force
# expensive, low enough to keep the login response fast on a laptop.
PBKDF2_ITERATIONS = 240_000
PBKDF2_SALT_BYTES = 16
PBKDF2_HASH_BYTES = 32

# The demo password.  It may only be used when the application explicitly runs
# in a local / demo environment (see ``NAVACITY_ENV``).
DEMO_PASSWORD = "dumpme"


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def b64encode(raw: bytes) -> str:
    """URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def b64decode(text: str) -> bytes:
    """Inverse of :func:`b64encode`."""
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def hash_password(password: str, *, salt: bytes | None = None) -> tuple[str, str]:
    """Return ``(salt_hex, hash_hex)`` for the given password.

    The salt is generated randomly when it is not supplied.  The same salt and
    hash always reproduce the same verification result.
    """
    if salt is None:
        salt = secrets.token_bytes(PBKDF2_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS, PBKDF2_HASH_BYTES
    )
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    """Constant-time verification of a password against a stored hash."""
    try:
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hash_hex)
    except (ValueError, TypeError):
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS, len(expected)
    )
    return hmac.compare_digest(digest, expected)


# --------------------------------------------------------------------------
# Session tokens
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class SessionPayload:
    """The decoded content of an authority session token."""

    session_id: str
    issued_at: int
    expires_at: int
    role: str = "authority"


def issue_token(
    payload: SessionPayload, secret: str
) -> str:
    """Sign a session payload and return the compact token."""
    body = json.dumps(
        {
            "sid": payload.session_id,
            "iat": payload.issued_at,
            "exp": payload.expires_at,
            "role": payload.role,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    encoded = b64encode(body)
    signature = hmac.new(
        secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256
    ).digest()
    return f"{encoded}.{b64encode(signature)}"


def decode_token(token: str, secret: str) -> SessionPayload | None:
    """Verify a token and return its payload, or ``None`` when it is invalid.

    A token is invalid when it is malformed, when the signature does not
    match, or when it has expired.  The server-side revocation check is *not*
    done here; that is the job of the session registry.
    """
    if not token or "." not in token:
        return None
    encoded, _, signature_part = token.partition(".")
    try:
        signature = b64decode(signature_part)
    except Exception:  # noqa: BLE001 - any decoding problem means "invalid"
        return None

    expected = hmac.new(
        secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256
    ).digest()
    if not hmac.compare_digest(signature, expected):
        return None

    try:
        body = json.loads(b64decode(encoded).decode("utf-8"))
        payload = SessionPayload(
            session_id=str(body["sid"]),
            issued_at=int(body["iat"]),
            expires_at=int(body["exp"]),
            role=str(body.get("role", "authority")),
        )
    except Exception:  # noqa: BLE001 - malformed payload means "invalid"
        return None

    if payload.expires_at <= int(time.time()):
        return None
    return payload
