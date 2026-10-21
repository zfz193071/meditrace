"""Validated runtime configuration; no dotenv loading, network or credentials in errors."""

import os
from collections.abc import Mapping
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator, model_validator


class ConfigurationError(ValueError):
    """Safe to display: messages contain field names, never supplied values."""


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    environment: Literal["development", "test", "production"] = Field("development", alias="RR_ENVIRONMENT")
    mode: Literal["bundled_demo", "sandbox", "invited_real"] = Field("bundled_demo", alias="RR_MODE")
    database_url: SecretStr | None = Field(None, alias="DATABASE_URL", repr=False)
    site_origin: str | None = Field(None, alias="RR_SITE_ORIGIN")
    github_client_id: str | None = Field(None, alias="RR_GITHUB_CLIENT_ID", repr=False)
    github_client_secret: SecretStr | None = Field(None, alias="RR_GITHUB_CLIENT_SECRET", repr=False)
    github_callback_url: str | None = Field(None, alias="RR_GITHUB_CALLBACK_URL")
    session_encryption_key: SecretStr | None = Field(None, alias="RR_SESSION_ENCRYPTION_KEY", repr=False)
    blob_token: SecretStr | None = Field(None, alias="BLOB_READ_WRITE_TOKEN", repr=False)
    storage_backend: Literal["disabled", "local", "vercel"] = Field("disabled", alias="RR_STORAGE_BACKEND")
    private_storage_dir: str | None = Field(None, alias="RR_PRIVATE_STORAGE_DIR", repr=False)
    storage_global_bytes: int = Field(1024**3, ge=0, alias="RR_STORAGE_GLOBAL_BYTES")
    stripe_secret_key: SecretStr | None = Field(None, alias="RR_STRIPE_SECRET_KEY", repr=False)
    stripe_webhook_secret: SecretStr | None = Field(None, alias="RR_STRIPE_WEBHOOK_SECRET", repr=False)
    stripe_price_id: str | None = Field(None, alias="RR_STRIPE_PRICE_ID", repr=False)
    stripe_amount_minor: int = Field(0, ge=0, alias="RR_STRIPE_AMOUNT_MINOR")
    stripe_currency: str = Field("usd", pattern=r"^[a-z]{3}$", alias="RR_STRIPE_CURRENCY")
    real_ai_enabled: bool = Field(False, alias="REAL_AI_ENABLED")
    deepseek_key: SecretStr | None = Field(None, alias="DEEPSEEK_API_KEY", repr=False)
    model_id: str | None = Field(None, alias="RR_MODEL_ID")
    price_version: str | None = Field(None, alias="RR_MODEL_PRICE_VERSION")
    input_microusd_per_million: int = Field(0, ge=0, alias="RR_MODEL_INPUT_MICROUSD_PER_MILLION_TOKENS")
    output_microusd_per_million: int = Field(0, ge=0, alias="RR_MODEL_OUTPUT_MICROUSD_PER_MILLION_TOKENS")
    daily_budget_microusd: int = Field(0, ge=0, alias="RR_DAILY_BUDGET_MICROUSD")
    monthly_budget_microusd: int = Field(0, ge=0, alias="RR_MONTHLY_BUDGET_MICROUSD")
    real_ai_user_ids: tuple[UUID, ...] = Field((), alias="RR_REAL_AI_USER_IDS", repr=False)
    maintenance_token: SecretStr | None = Field(None, alias="RR_MAINTENANCE_TOKEN", repr=False)

    @field_validator("real_ai_user_ids", mode="before")
    @classmethod
    def parse_user_ids(cls, value):
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value

    @field_validator("stripe_secret_key")
    @classmethod
    def test_payments_only(cls, value):
        if value and not value.get_secret_value().startswith(("sk_test_", "rk_test_")):
            raise ValueError("Only Stripe test credentials are supported")
        return value

    @field_validator("session_encryption_key", "maintenance_token")
    @classmethod
    def minimum_secret_length(cls, value):
        if value and len(value.get_secret_value()) < 32:
            raise ValueError("At least 32 characters are required")
        return value

    @field_validator("site_origin", "github_callback_url")
    @classmethod
    def validate_url(cls, value):
        if value is None:
            return value
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("A plain HTTP(S) URL is required")
        return value.rstrip("/")

    @model_validator(mode="after")
    def secure_origins(self):
        if self.storage_backend == "local":
            if self.environment == "production" or not self.private_storage_dir:
                raise ValueError("Local storage requires a private directory and a non-production environment")
        if self.storage_backend == "vercel" and not self.blob_token:
            raise ValueError("Private Blob requires a server token")
        if self.site_origin and urlsplit(self.site_origin).path:
            raise ValueError("RR_SITE_ORIGIN must not contain a path")
        if self.github_callback_url:
            if not self.site_origin or self.github_callback_url != self.site_origin + "/api/v1/auth/github/callback":
                raise ValueError("OAuth callback must use the configured site origin")
        if self.environment == "production":
            for value in (self.site_origin, self.github_callback_url):
                if value and urlsplit(value).scheme != "https":
                    raise ValueError("Production origins require HTTPS")
            if self.database_url and not self.database_url.get_secret_value().startswith(("postgresql://", "postgres://", "postgresql+psycopg2://")):
                raise ValueError("Production persistence requires PostgreSQL")
        return self

    def require_real_ai_configuration(self) -> None:
        """A configuration precondition, NOT identity, membership or budget authorization.

        MT-10/11 must also reserve shared quotas and verify the authenticated user.
        Never use successful configuration validation as permission to call a model.
        """
        if not all((
            self.mode == "invited_real", self.real_ai_enabled, self.deepseek_key,
            self.model_id, self.price_version, self.real_ai_user_ids,
            self.input_microusd_per_million > 0, self.output_microusd_per_million > 0,
            self.daily_budget_microusd > 0, self.monthly_budget_microusd > 0,
        )):
            raise ConfigurationError("Real AI configuration is incomplete or disabled")


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if environ is None else environ
    names = {field.alias for field in Settings.model_fields.values()}
    # Unknown RR_ switches fail closed, including fake identity / dev grant switches.
    if any(name.startswith("RR_") and name not in names for name in env):
        raise ConfigurationError("Unknown referral configuration option")
    values = {name: env[name] for name in names if name in env and env[name] != ""}
    # A deployed process cannot downgrade itself to development through RR_ENVIRONMENT.
    if env.get("VERCEL") == "1" or env.get("VERCEL_ENV") in ("preview", "production"):
        if values.get("RR_ENVIRONMENT", "production") != "production":
            raise ConfigurationError("Deployed referral applications require production configuration")
        values["RR_ENVIRONMENT"] = "production"
    try:
        return Settings.model_validate(values)
    except ValidationError:
        raise ConfigurationError("Invalid referral configuration; check the documented variable types and constraints") from None
