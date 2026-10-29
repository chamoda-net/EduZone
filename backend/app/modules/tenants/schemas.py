from pydantic import BaseModel


class TenantBranding(BaseModel):
    """What the frontend needs to brand a tenant's site. No money or plan settings."""

    name: str
    slug: str
    logo_url: str | None
    primary_color: str | None
