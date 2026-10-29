from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# The repo-root .env is shared with docker-compose.
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    environment: str = "local"
    base_domain: str = "eduzone.lk"

    # eduzone_app: tenant-facing requests, subject to RLS.
    database_url: str
    # eduzone_admin: platform admin endpoints and background jobs only (BYPASSRLS).
    admin_database_url: str
    # Schema owner: Alembic only. Never used by the running app.
    migration_database_url: str

    redis_url: str = "redis://localhost:6379/0"

    # --- Auth -----------------------------------------------------------------
    # Signing key for access JWTs. At least 32 random bytes in production.
    jwt_secret: str = Field(min_length=32)
    # HMAC key for OTP code hashes (kept separate so one leak doesn't expose both).
    otp_secret: str = Field(min_length=32)
    access_token_ttl_seconds: int = 15 * 60
    refresh_token_ttl_days: int = 30

    otp_ttl_seconds: int = 5 * 60
    otp_max_attempts: int = 5            # wrong guesses per code
    otp_resend_cooldown_seconds: int = 60
    otp_max_per_phone_per_hour: int = 5
    otp_max_per_ip_per_hour: int = 20

    # 'console' logs the message (local dev). Real providers are added behind
    # app.integrations.sms once one is chosen.
    sms_provider: Literal["console"] = "console"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from env / .env
