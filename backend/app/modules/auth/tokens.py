"""OTP hashing, refresh tokens and access JWTs."""

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


def hash_otp(phone: str, code: str) -> str:
    key = get_settings().otp_secret.encode()
    return hmac.new(key, f"login:{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def otp_matches(stored_hash: str, phone: str, code: str) -> bool:
    return hmac.compare_digest(stored_hash, hash_otp(phone, code))


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    # The token is 256 random bits, so a plain hash is enough (no salt or KDF needed).
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class AccessClaims:
    user_id: UUID
    tenant_id: UUID
    member_id: UUID
    role: str
    session_id: UUID


def issue_access_token(claims: AccessClaims) -> str:
    settings = get_settings()
    now = int(time.time())
    payload = {
        "typ": "access",
        "sub": str(claims.user_id),
        "tid": str(claims.tenant_id),
        "mid": str(claims.member_id),
        "role": claims.role,
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
            options={"require": ["exp", "iat", "sub", "tid", "mid", "sid", "typ"]},
        )
        if payload["typ"] != "access":
            raise jwt.InvalidTokenError("wrong token type")
        return AccessClaims(
            user_id=UUID(payload["sub"]),
            tenant_id=UUID(payload["tid"]),
            member_id=UUID(payload["mid"]),
            role=str(payload.get("role", "")),
            session_id=UUID(payload["sid"]),
        )
    except (jwt.PyJWTError, ValueError) as exc:
        raise ApiError("UNAUTHORIZED", "Please sign in again.", status_code=401) from exc
