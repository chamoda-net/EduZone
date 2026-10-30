"""Private files (applicants' ID and business documents). Never served by the CDN: they are stored
by key and read back only through the API by the platform admin."""

import asyncio
from pathlib import Path
from typing import Annotated, Protocol

import httpx
from fastapi import Depends

from app.core.config import get_settings
from app.core.errors import ApiError
from app.integrations.bunny import bunny_http, not_configured
from app.integrations.bunny.storage import StorageClient


class PrivateStorage(Protocol):
    async def put(self, key: str, content: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...


class LocalPrivateStorage:
    """Development and tests: files under a local folder (ENVIRONMENT=local only)."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ApiError("NOT_FOUND", "File not found.", status_code=404)
        return path

    async def put(self, key: str, content: bytes, content_type: str) -> None:
        path = self._path(key)
        await asyncio.to_thread(lambda: (path.parent.mkdir(parents=True, exist_ok=True), path.write_bytes(content)))

    async def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise ApiError("NOT_FOUND", "File not found.", status_code=404)
        return await asyncio.to_thread(path.read_bytes)


class BunnyPrivateStorage:
    """Production: the Bunny Storage zone, under _private/ (never given a signed CDN URL)."""

    def __init__(self, client: StorageClient) -> None:
        self.client = client

    async def put(self, key: str, content: bytes, content_type: str) -> None:
        await self.client.upload(f"_private/{key}", content, content_type)

    async def get(self, key: str) -> bytes:
        return await self.client.download(f"_private/{key}")


def get_private_storage(http: Annotated[httpx.AsyncClient, Depends(bunny_http)]) -> PrivateStorage:
    """FastAPI dependency (tests override it)."""
    s = get_settings()
    if s.private_storage == "local":
        if s.environment != "local":
            raise not_configured("Private storage")
        return LocalPrivateStorage(s.private_storage_dir)
    if not (s.bunny_storage_zone and s.bunny_storage_api_key):
        raise not_configured("Private storage")
    return BunnyPrivateStorage(StorageClient(http, s.bunny_storage_host, s.bunny_storage_zone, s.bunny_storage_api_key))
