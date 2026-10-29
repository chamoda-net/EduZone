"""Bunny signatures. Pure functions: no network, easy to test.

Formulas follow Bunny's documentation; re-check them against a real library before launch.
"""

import base64
import hashlib


def tus_signature(library_id: int, api_key: str, expires: int, video_id: str) -> str:
    """Pre-signed TUS upload: SHA256_HEX(library_id + api_key + expiration_time + video_id)."""
    return hashlib.sha256(f"{library_id}{api_key}{expires}{video_id}".encode()).hexdigest()


def embed_url(embed_base: str, library_id: int, video_id: str, token_key: str, expires: int) -> str:
    """Stream embed URL with token authentication: SHA256_HEX(token_key + video_id + expires)."""
    token = hashlib.sha256(f"{token_key}{video_id}{expires}".encode()).hexdigest()
    return f"{embed_base}/embed/{library_id}/{video_id}?token={token}&expires={expires}"


def cdn_url(cdn_host: str, path: str, token_key: str, expires: int) -> str:
    """Pull-zone URL with token authentication:
    Base64Url(SHA256_RAW(token_key + path + expires)) without padding."""
    if not path.startswith("/"):
        path = "/" + path
    digest = hashlib.sha256(f"{token_key}{path}{expires}".encode()).digest()
    token = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return f"https://{cdn_host}{path}?token={token}&expires={expires}"
