"""The visitor's address: believed only from our own web server, and never for network access."""

import secrets

import pytest
from httpx import AsyncClient
from starlette.requests import Request

from app.core.config import get_settings
from app.main import check_settings
from app.modules.auth.dependencies import client_ip, peer_ip

KEY = "k" * 40


def make(peer: str = "10.0.0.5", **headers: str) -> Request:
    raw = [(k.replace("_", "-").encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "headers": raw, "client": (peer, 1)})


@pytest.fixture
def key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "web_server_key", KEY)


def test_our_web_server_names_the_visitor(key: None) -> None:
    r = make(x_eduzone_web_key=KEY, x_eduzone_client_ip="203.0.113.9")
    assert client_ip(r) == "203.0.113.9" and peer_ip(r) == "10.0.0.5"
    assert client_ip(make(x_eduzone_web_key=KEY, x_eduzone_client_ip="::ffff:203.0.113.9")) == "203.0.113.9"
    assert client_ip(make(x_eduzone_web_key=KEY, x_eduzone_client_ip="2001:db8::1")) == "2001:db8::1"


@pytest.mark.parametrize("headers", [
    {"x_eduzone_client_ip": "203.0.113.9"},
    {"x_eduzone_web_key": "wrong", "x_eduzone_client_ip": "203.0.113.9"},
    {"x_eduzone_web_key": "", "x_eduzone_client_ip": "203.0.113.9"},
    {"x_eduzone_web_key": "k\u00e9", "x_eduzone_client_ip": "203.0.113.9"},
    {"x_eduzone_web_key": KEY, "x_eduzone_client_ip": "not-an-address"},
    {"x_eduzone_web_key": KEY},
    {"x_forwarded_for": "203.0.113.9"},
])
def test_anyone_else_is_their_own_address(key: None, headers: dict[str, str]) -> None:
    assert client_ip(make(**headers)) == "10.0.0.5"


def test_no_key_means_the_header_is_never_believed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "web_server_key", None)
    assert client_ip(make(x_eduzone_web_key="", x_eduzone_client_ip="203.0.113.9")) == "10.0.0.5"


async def test_one_visitor_does_not_block_another(client: AsyncClient, key: None,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "login_max_failures_per_ip", 2)

    async def sign_in(visitor: str, n: int) -> str:
        r = await client.post("/api/v1/auth/login", headers={"x-eduzone-web-key": KEY, "x-eduzone-client-ip": visitor},
                              json={"email": f"nobody-ip-{visitor.replace('.', '-')}-{n}@example.com",
                                    "password": "not-a-password", "device_id": "device-0001"})
        return r.json()["error"]["code"]

    a, b = (f"10.{secrets.randbelow(256)}.{secrets.randbelow(256)}.{n}" for n in (1, 2))
    assert [await sign_in(a, n) for n in range(3)] == ["LOGIN_EMAIL_UNKNOWN"] * 2 + ["LOGIN_RATE_LIMITED"]
    assert await sign_in(b, 0) == "LOGIN_EMAIL_UNKNOWN"


async def test_platform_network_ignores_the_named_address(client: AsyncClient, key: None,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    """Holding the web server's key must not open the admin API."""
    monkeypatch.setattr(get_settings(), "platform_allowed_cidrs", ["192.0.2.7/32"])
    r = await client.post("/api/v1/platform/auth/otp/request", json={"phone": "+94770000000"},
                          headers={"x-eduzone-web-key": KEY, "x-eduzone-client-ip": "192.0.2.7"})
    assert r.status_code == 404


def test_the_key_is_required_outside_local(monkeypatch: pytest.MonkeyPatch) -> None:
    s = get_settings()
    monkeypatch.setattr(s, "web_server_key", None)
    check_settings()
    monkeypatch.setattr(s, "environment", "production")
    with pytest.raises(RuntimeError, match="WEB_SERVER_KEY"):
        check_settings()
    monkeypatch.setattr(s, "web_server_key", KEY)
    check_settings()
