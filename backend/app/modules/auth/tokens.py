"""OTP hashing, opaque tokens (refresh, links) and signed JWTs (access, device challenge)."""

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from uuid import UUID

import jwt

from app.core.config import get_settings
from app.core.errors import ApiError

_ALGORITHM = "HS256"


def new_otp_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def hash_otp(destination: str, code: str, purpose: str = "login") -> str:
    key = get_settings().otp_secret.encode()
    return hmac.new(key, f"{purpose}:{destination}:{code}".encode(), hashlib.sha256).hexdigest()


def otp_matches(stored_hash: str, destination: str, code: str, purpose: str = "login") -> bool:
    return hmac.compare_digest(stored_hash, hash_otp(destination, code, purpose))


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def new_link_token() -> str:
    """For email links (verification, recovery); stored only as a hash."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    # The token is 256 random bits, so a plain hash is enough (no salt or KDF needed).
    return hashlib.sha256(token.encode()).hexdigest()


hash_link_token = hash_refresh_token


@dataclass(frozen=True, slots=True)
class AccessClaims:
    """Accounts are global: the token names the user and the session, never a tenant.
    Role and membership are looked up per request for the tenant being used."""

    user_id: UUID
    session_id: UUID


def issue_access_token(claims: AccessClaims) -> str:
    settings = get_settings()
    now = int(time.time())
    payload = {
        "typ": "access",
        "sub": str(claims.user_id),
        "sid": str(claims.session_id),
        "iat": now,
        "exp": now + settings.access_token_ttl_seconds,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> AccessClaims:
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[_ALGORITHM],
            options={"require": ["exp", "iat", "sub", "sid", "typ"]},
        )
        if payload["typ"] != "access":
            raise jwt.InvalidTokenError("wrong token type")
        return AccessClaims(user_id=UUID(payload["sub"]), session_id=UUID(payload["sid"]))
    except (jwt.PyJWTError, ValueError) as exc:
        raise ApiError("UNAUTHORIZED", "Please sign in again.", status_code=401) from exc


# --- New-device challenge ---------------------------------------------------------------
# Password (or Google) was right but the device is unknown: the client gets this signed,
# short-lived ticket and must send it back with the SMS code. Nothing is stored server-side
# except the OTP itself.


@dataclass(frozen=True, slots=True)
class DeviceChallenge:
    user_id: UUID
    device_id: str


def issue_device_challenge(user_id: UUID, device_id: str) -> str:
    settings = get_settings()
    now = int(time.time())
    payload = {"typ": "device", "sub": str(user_id), "dev": device_id, "iat": now,
               "exp": now + settings.device_challenge_ttl_seconds}
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_device_challenge(token: str) -> DeviceChallenge:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[_ALGORITHM],
                             options={"require": ["exp", "sub", "dev", "typ"]})
        if payload["typ"] != "device":
            raise jwt.InvalidTokenError("wrong token type")
        return DeviceChallenge(UUID(payload["sub"]), str(payload["dev"]))
    except (jwt.PyJWTError, ValueError) as exc:
        raise ApiError("CHALLENGE_EXPIRED", "This sign-in has expired. Please sign in again.", 401) from exc
