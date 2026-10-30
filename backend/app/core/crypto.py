"""Encryption for the few stored secrets that must be read back (bank account numbers)."""

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.errors import ApiError


@lru_cache
def _fernet() -> Fernet:
    s = get_settings()
    if s.payout_encryption_key:
        return Fernet(s.payout_encryption_key.encode())
    if s.environment != "local":
        raise ApiError("PAYOUT_NOT_CONFIGURED", "Payout details can't be stored right now.", status_code=503)
    # Development only: a stable key derived from the JWT secret.
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"payout:" + s.jwt_secret.encode()).digest()))


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ApiError("DECRYPT_FAILED", "This value can't be read with the current key.", status_code=500) from exc


def mask_account(number: str) -> str:
    digits = "".join(ch for ch in number if ch.isalnum())
    return f"****{digits[-4:]}" if len(digits) >= 4 else "****"
