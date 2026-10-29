"""Bunny Stream (video) API client. One instance per tenant library."""

from dataclasses import dataclass

import httpx

from app.core.errors import ApiError


@dataclass(frozen=True, slots=True)
class StreamVideo:
    guid: str
    status: int              # Bunny's video status code (see video_status)
    length_seconds: int
    storage_size: int


def video_status(code: int) -> str:
    """Map Bunny's video status to media_assets.status.

    Bunny video object status: 0 created, 1 uploaded, 2 processing, 3 transcoding,
    4 finished, 5 error, 6 upload failed (7/8 are JIT stages, still processing).
    """
    if code == 0:
        return "uploading"
    if code == 4:
        return "ready"
    if code in (5, 6):
        return "failed"
    return "processing"


def _bunny_down() -> ApiError:
    return ApiError("MEDIA_PROVIDER_ERROR", "The video service did not respond. Please try again.", 502)


class StreamClient:
    def __init__(self, http: httpx.AsyncClient, api_base: str, library_id: int, api_key: str) -> None:
        self._http = http
        self._base = f"{api_base}/library/{library_id}/videos"
        self._headers = {"AccessKey": api_key, "accept": "application/json"}

    async def create_video(self, title: str) -> str:
        """Creates an empty video and returns its GUID (the upload then goes straight to Bunny)."""
        try:
            res = await self._http.post(self._base, json={"title": title}, headers=self._headers)
            res.raise_for_status()
            return str(res.json()["guid"])
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise _bunny_down() from exc

    async def get_video(self, guid: str) -> StreamVideo | None:
        try:
            res = await self._http.get(f"{self._base}/{guid}", headers=self._headers)
            if res.status_code == 404:
                return None
            res.raise_for_status()
            data = res.json()
            return StreamVideo(
                guid=guid,
                status=int(data.get("status", 0)),
                length_seconds=int(data.get("length") or 0),
                storage_size=int(data.get("storageSize") or 0),
            )
        except (httpx.HTTPError, ValueError) as exc:
            raise _bunny_down() from exc

    async def delete_video(self, guid: str) -> None:
        try:
            res = await self._http.delete(f"{self._base}/{guid}", headers=self._headers)
            if res.status_code != 404:
                res.raise_for_status()
        except httpx.HTTPError as exc:
            raise _bunny_down() from exc
