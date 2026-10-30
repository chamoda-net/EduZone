from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# The repo-root .env is shared with docker-compose.
REPO_ROOT = Path(__file__).resolve().parents[3]


class BunnyLibraryKeys(BaseModel):
    api_key: str                 # library API key: create/read/delete videos, sign TUS uploads
    token_key: str               # embed token authentication key: signs playback URLs


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

    # 'console' logs the message (local dev); 'file' appends it to sms_outbox_path as JSON
    # lines for browser tests (ENVIRONMENT=local only). Real providers are added behind
    # app.integrations.sms once one is chosen.
    sms_provider: Literal["console", "file"] = "console"
    sms_outbox_path: Path = Path("sms-outbox.jsonl")

    # --- Identity (CLAUDE.md section 11) ---------------------------------------------
    password_min_length: int = 8
    # Password sign-in throttling, counted over login_window_minutes.
    login_window_minutes: int = 15
    login_max_failures_per_email: int = 8
    login_max_failures_per_ip: int = 30
    # A sign-in from an unknown device must be confirmed by SMS within this time.
    device_challenge_ttl_seconds: int = 10 * 60
    email_verification_ttl_hours: int = 48
    recovery_ttl_minutes: int = 30
    # Google sign-in (OpenID Connect). Unset = Google sign-in is off (503 GOOGLE_NOT_CONFIGURED).
    google_client_id: str | None = None
    # Email: 'console' logs it, 'file' appends JSON lines to email_outbox_path (ENVIRONMENT=local
    # only). A real provider is added behind app.integrations.email once one is chosen.
    email_provider: Literal["console", "file"] = "console"
    email_outbox_path: Path = Path("email-outbox.jsonl")
    email_from: str = "EduZone <no-reply@eduzone.switchops.tech>"

    # --- Teacher applications (CLAUDE.md section 2) -----------------------------------
    # Version of the teacher terms an applicant accepts (stored on the application).
    teacher_terms_version: str = "2026-10-draft"
    # Private documents (ID / business registration): 'local' writes to private_storage_dir
    # (ENVIRONMENT=local only); 'bunny' uses the Bunny Storage zone under _private/, never signed
    # for the CDN, read back only through the API.
    private_storage: Literal["local", "bunny"] = "local"
    private_storage_dir: Path = Path("private-storage")
    # Fernet key (urlsafe base64, 32 bytes) for bank account numbers. Required outside
    # ENVIRONMENT=local; locally a key is derived from JWT_SECRET.
    payout_encryption_key: str | None = None

    # --- Bunny (CLAUDE.md section 9) ---------------------------------------------
    # One Stream library per tenant (tenants.bunny_library_id). Keys per library come from
    # the environment as JSON: {"<library_id>": {"api_key": "...", "token_key": "..."}}.
    bunny_stream_libraries: dict[str, BunnyLibraryKeys] = {}
    bunny_stream_api_base: str = "https://video.bunnycdn.com"
    bunny_stream_tus_endpoint: str = "https://video.bunnycdn.com/tusupload"
    bunny_stream_embed_base: str = "https://iframe.mediadelivery.net"
    # Shared secret in the Stream webhook URL (?token=...); unset disables the webhook.
    bunny_webhook_token: str | None = None
    # PDFs: one storage zone, files under /<tenant_id>/..., served by a pull zone with
    # token authentication. All unset = document uploads are disabled.
    bunny_storage_zone: str | None = None
    bunny_storage_host: str = "storage.bunnycdn.com"   # regional, e.g. sg.storage.bunnycdn.com
    bunny_storage_api_key: str | None = None
    bunny_cdn_host: str | None = None                  # e.g. eduzone-files.b-cdn.net
    bunny_cdn_token_key: str | None = None

    upload_signature_ttl_seconds: int = 12 * 3600      # slow connections, big lessons
    video_url_ttl_seconds: int = 4 * 3600              # a long lesson must not expire mid-way
    document_url_ttl_seconds: int = 10 * 60
    max_video_bytes: int = 10 * 1024**3
    max_document_bytes: int = 50 * 1024**2

    # --- Payments (CLAUDE.md section 8) ---------------------------------------------
    # 'fake' is a local stand-in (ENVIRONMENT=local only); 'payhere' needs the merchant keys.
    payment_gateway: Literal["fake", "payhere"] = "fake"
    payhere_merchant_id: str | None = None
    payhere_merchant_secret: str | None = None
    payhere_sandbox: bool = True
    # Gateway fee booked at sale time, in basis points; trued up from the settlement report.
    # Set from the merchant agreement.
    gateway_fee_estimate_bps: int = Field(default=300, ge=0, le=10000)
    # Public base URL of this API (the gateway calls {api_public_url}/api/v1/webhooks/<gateway>).
    api_public_url: str = "http://localhost:8000"
    # Scheme the tenant sites are served on (for return URLs built from the user's host).
    site_scheme: Literal["http", "https"] = "https"

    # --- Platform admin (EduZone staff) --------------------------------------------
    # Client networks allowed to reach /api/v1/platform (e.g. the VPN). Empty = any network,
    # which is refused outside ENVIRONMENT=local.
    platform_allowed_cidrs: list[str] = []
    platform_access_ttl_seconds: int = 15 * 60
    platform_session_hours: int = 12            # admins sign in again at least twice a day


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from env / .env
