"""Google sign-in: the browser gets an ID token from Google; we verify it server-side."""

from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import jwt

from app.core.config import get_settings
from app.core.errors import ApiError

_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_ISSUERS = ("https://accounts.google.com", "accounts.google.com")


@dataclass(frozen=True, slots=True)
class GoogleIdentity:
    subject: str
    email: str | None
    email_verified: bool
    name: str | None


class GoogleVerifier(Protocol):
    def verify(self, id_token: str) -> GoogleIdentity: ...


class JwksGoogleVerifier:
    """Checks the signature against Google's published keys, then audience, issuer and expiry."""

    def __init__(self, client_id: str) -> None:
        self.client_id = client_id
        self._jwks = jwt.PyJWKClient(_JWKS_URL, cache_keys=True, lifespan=3600)

    def verify(self, id_token: str) -> GoogleIdentity:
        try:
            key = self._jwks.get_signing_key_from_jwt(id_token)
            claims = jwt.decode(id_token, key.key, algorithms=["RS256"], audience=self.client_id,
                                options={"require": ["exp", "iat", "iss", "aud", "sub"]})
        except jwt.PyJWTError as exc:
            raise _invalid() from exc
        if claims.get("iss") not in _ISSUERS:
            raise _invalid()
        return GoogleIdentity(
            subject=str(claims["sub"]),
            email=claims.get("email"),
            email_verified=bool(claims.get("email_verified")),
            name=claims.get("name"),
        )


def _invalid() -> ApiError:
    return ApiError("GOOGLE_TOKEN_INVALID", "Google sign-in didn't work. Please try again.", 401)


@lru_cache
def _verifier(client_id: str) -> JwksGoogleVerifier:
    return JwksGoogleVerifier(client_id)


def get_google_verifier() -> GoogleVerifier:
    """FastAPI dependency (tests override it with a fake)."""
    client_id = get_settings().google_client_id
    if not client_id:
        raise ApiError("GOOGLE_NOT_CONFIGURED", "Google sign-in isn't available yet.", 503)
    return _verifier(client_id)
