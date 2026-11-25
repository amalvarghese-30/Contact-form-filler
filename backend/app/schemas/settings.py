"""Field mapping, notification, and settings schemas."""

from typing import Optional
from pydantic import BaseModel, Field


class FieldMappingUpdateRequest(BaseModel):
    normalized_label: str = Field(..., min_length=1, max_length=255)
    canonical_concept: str = Field(..., min_length=1, max_length=100)


class RandomValueCreateRequest(BaseModel):
    field_concept: str = Field(..., min_length=1, max_length=64)
    value: str = Field(..., min_length=1, max_length=2000)


class EmailConfigRequest(BaseModel):
    smtp_host: str = Field(..., min_length=1, max_length=255)
    smtp_port: int = Field(..., ge=1, le=65535)
    smtp_user: str = Field(..., min_length=1, max_length=255)
    smtp_password: Optional[str] = None
    from_name: str = Field(default="Contact Form Filler", max_length=255)
    is_enabled: bool = True


class NotificationEmailCreateRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)


class AutomationSettingsUpdateRequest(BaseModel):
    headless: Optional[bool] = None
    concurrency: Optional[int] = Field(default=None, ge=1, le=10)
    per_website_timeout_sec: Optional[int] = Field(default=None, ge=10, le=300)
    action_timeout_ms: Optional[int] = Field(default=None, ge=1000, le=60000)
    post_submit_wait_ms: Optional[int] = Field(default=None, ge=500, le=30000)
    polite_delay_ms: Optional[int] = Field(default=None, ge=0, le=10000)
    max_retries: Optional[int] = Field(default=None, ge=0, le=5)
    dry_run: Optional[bool] = None
