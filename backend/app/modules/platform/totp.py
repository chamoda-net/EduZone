"""Time-based one-time passwords (RFC 6238: HMAC-SHA1, 30 s steps, 6 digits), the codes
shown by authenticator apps. Small enough to keep in-house rather than add a dependency."""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

STEP_SECONDS = 30
DIGITS = 6


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _code(secret: str, step: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**DIGITS).zfill(DIGITS)


def current_step(now: float | None = None) -> int:
    return int((now if now is not None else time.time()) // STEP_SECONDS)


def code_at(secret: str, step: int) -> str:
    return _code(secret, step)


def verify(secret: str, code: str, *, last_used_step: int, now: float | None = None) -> int | None:
    """The matching step (one step of clock drift either way), or None. A step at or before
    `last_used_step` is refused, so a code seen over someone's shoulder can't be replayed."""
    if not (code.isdigit() and len(code) == DIGITS):
        return None
    now_step = current_step(now)
    for step in (now_step - 1, now_step, now_step + 1):
        if step > last_used_step and hmac.compare_digest(_code(secret, step), code):
            return step
    return None


def provisioning_uri(secret: str, account: str, issuer: str = "EduZone Admin") -> str:
    """otpauth:// link (or QR code) for adding the secret to an authenticator app."""
    return (f"otpauth://totp/{quote(issuer)}:{quote(account)}?secret={secret}&issuer={quote(issuer)}"
            f"&algorithm=SHA1&digits={DIGITS}&period={STEP_SECONDS}")
