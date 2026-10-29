from functools import lru_cache
from pathlib import Path

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


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from env / .env
