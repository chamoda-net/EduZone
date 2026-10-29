"""Bunny.net: Stream for video, Storage for PDFs. Keys come from settings (env), never the DB."""

import httpx

from app.core.config import get_settings
from app.core.errors import ApiError
from app.integrations.bunny.storage import StorageClient
from app.integrations.bunny.stream import StreamClient

_http: httpx.AsyncClient | None = None


def bunny_http() -> httpx.AsyncClient:
    """Shared HTTP client for Bunny calls. A FastAPI dependency so tests can swap in a fake."""
    global _http
    if _http is None:
        _http = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0))
    return _http


async def close_bunny_http() -> None:
    global _http
    if _http is not None:
        await _http.aclose()
        _http = None


def not_configured(what: str) -> ApiError:
    return ApiError("MEDIA_NOT_CONFIGURED", f"{what} is not set up for this organization yet.", 503)


def stream_client(http: httpx.AsyncClient, library_id: int | None) -> tuple[StreamClient, int, str]:
    """Client for a tenant's library, plus its library id and embed token key."""
    s = get_settings()
    keys = s.bunny_stream_libraries.get(str(library_id)) if library_id is not None else None
    if library_id is None or keys is None:
        raise not_configured("Video")
    return StreamClient(http, s.bunny_stream_api_base, library_id, keys.api_key), library_id, keys.token_key


def storage_client(http: httpx.AsyncClient) -> StorageClient:
    s = get_settings()
    if not (s.bunny_storage_zone and s.bunny_storage_api_key and s.bunny_cdn_host and s.bunny_cdn_token_key):
        raise not_configured("File storage")
    return StorageClient(http, s.bunny_storage_host, s.bunny_storage_zone, s.bunny_storage_api_key)
