"""
DramaZone VIP Bot System
========================
Central configuration management.
All secrets come from environment variables — nothing is hard-coded.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    pydantic-settings automatically reads from .env when python-dotenv is installed.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Telegram Bot Tokens ──────────────────────────────────────────────────
    customer_bot_token: str
    admin_bot_token: str

    # ── MongoDB ──────────────────────────────────────────────────────────────
    mongodb_uri: str
    mongodb_db_name: str = "dramazone_vip"

    # ── Admin Authorization ───────────────────────────────────────────────────
    admin_telegram_ids_raw: str = ""  # comma-separated string from env

    @property
    def admin_telegram_ids(self) -> list[int]:
        """Parse ADMIN_TELEGRAM_IDS into a list of integers."""
        if not self.admin_telegram_ids_raw:
            return []
        return [
            int(tid.strip())
            for tid in self.admin_telegram_ids_raw.split(",")
            if tid.strip().isdigit()
        ]

    admin_username: str = "myatnyein21"

    # ── Payment ───────────────────────────────────────────────────────────────
    kpay_phone: str = ""
    kpay_account_name: str = ""
    wave_phone: str = ""
    wave_account_name: str = ""

    # ── Webhook Secrets ───────────────────────────────────────────────────────
    customer_webhook_secret: str = ""
    admin_webhook_secret: str = ""

    # ── QR Codes (optional — app works without these) ────────────────────────
    qr_kpay_file_id: Optional[str] = None
    qr_wave_file_id: Optional[str] = None

    # ── Hosting ───────────────────────────────────────────────────────────────
    base_webhook_url: str = ""  # e.g. https://your-app.onrender.com

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = "INFO"

    # ── Field aliases for env var names with underscores ─────────────────────
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # Map ADMIN_TELEGRAM_IDS env var → admin_telegram_ids_raw field
        populate_by_name=True,
    )

    @field_validator("customer_bot_token", "admin_bot_token", mode="before")
    @classmethod
    def token_must_not_be_empty(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(
                f"{info.field_name} must not be empty. "
                "Set it in your .env file."
            )
        return v.strip()

    @field_validator("mongodb_uri", mode="before")
    @classmethod
    def mongodb_uri_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(
                "MONGODB_URI must not be empty. "
                "Copy your Atlas connection string into .env"
            )
        return v.strip()

    @model_validator(mode="after")
    def warn_missing_optional(self) -> "Settings":
        if not self.base_webhook_url:
            logger.warning(
                "BASE_WEBHOOK_URL is not set. "
                "Webhook registration will be skipped."
            )
        if not self.customer_webhook_secret:
            logger.warning(
                "CUSTOMER_WEBHOOK_SECRET is not set. "
                "Webhook requests will not be validated."
            )
        if not self.admin_webhook_secret:
            logger.warning(
                "ADMIN_WEBHOOK_SECRET is not set. "
                "Webhook requests will not be validated."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached Settings instance.
    Call get_settings() everywhere — never instantiate Settings directly.
    This ensures the .env file is read exactly once.
    """
    return Settings()
