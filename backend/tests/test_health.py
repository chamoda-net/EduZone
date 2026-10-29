from httpx import AsyncClient


async def test_health_reaches_database(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "ok"}


async def test_unknown_route_uses_error_shape(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/nope")
    assert resp.status_code == 404
    assert resp.json() == {"error": {"code": "NOT_FOUND", "message": "Not Found"}}
