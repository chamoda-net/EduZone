"""Bunny Storage (files) client. Tenant files live under /<tenant_id>/... in one zone."""

import hashlib

import httpx

from app.core.errors import ApiError


def _storage_down() -> ApiError:
    return ApiError("MEDIA_PROVIDER_ERROR", "The file service did not respond. Please try again.", 502)


class StorageClient:
    def __init__(self, http: httpx.AsyncClient, host: str, zone: str, api_key: str) -> None:
        self._http = http
        self._base = f"https://{host}/{zone}"
        self._key = api_key

    async def upload(self, path: str, content: bytes, content_type: str) -> None:
        headers = {
            "AccessKey": self._key,
            "content-type": content_type,
            # Bunny rejects the upload if the stored bytes don't match.
            "Checksum": hashlib.sha256(content).hexdigest().upper(),
        }
        try:
            res = await self._http.put(f"{self._base}/{path.lstrip('/')}", content=content, headers=headers)
            res.raise_for_status()
        except httpx.HTTPError as exc:
            raise _storage_down() from exc

    async def delete(self, path: str) -> None:
        try:
            res = await self._http.delete(f"{self._base}/{path.lstrip('/')}", headers={"AccessKey": self._key})
            if res.status_code != 404:
                res.raise_for_status()
        except httpx.HTTPError as exc:
            raise _storage_down() from exc

    async def download(self, path: str) -> bytes:
        try:
            res = await self._http.get(f"{self._base}/{path.lstrip('/')}", headers={"AccessKey": self._key})
            if res.status_code == 404:
                raise ApiError("NOT_FOUND", "File not found.", status_code=404)
            res.raise_for_status()
            return res.content
        except httpx.HTTPError as exc:
            raise _storage_down() from exc
