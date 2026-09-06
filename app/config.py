"""
app/config.py
Central configuration loaded from environment variables.
All settings are read once at startup via pydantic-settings.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings.

    Values are read from the environment (or .env file).
    Secrets are NEVER hard-coded or logged.
    """

    model_config = SettingsConfigDict(
        # Load .env automatically when present (local dev).
        # In production, real env-vars take priority.
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Telegram ─────────────────────────────────────────────────────────────
    customer_bot_token: str = ""
    admin_bot_token: str = ""

    # ── MongoDB ───────────────────────────────────────────────────────────────
    mongodb_uri: str = ""
    mongodb_db_name: str = "dramazone_vip"

    # ── Admins ────────────────────────────────────────────────────────────────
    # Stored as comma-separated string in env; parsed to a list of ints.
    admin_telegram_ids: str = "1673861706,1655754454"
    admin_username: str = "myatnyein21"

    # ── Payment ───────────────────────────────────────────────────────────────
    kpay_phone: str = ""
    kpay_account_name: str = ""
    wave_phone: str = ""
    wave_account_name: str = ""

    # ── QR codes (optional Telegram file IDs) ────────────────────────────────
    qr_kpay_file_id: str = ""
    qr_wave_file_id: str = ""

    # ── Webhook ───────────────────────────────────────────────────────────────
    customer_webhook_secret: str = ""
    admin_webhook_secret: str = ""
    webhook_base_url: str = ""

    # ── Deployment mode ───────────────────────────────────────────────────────
    # 'polling' for local dev, 'webhook' for production
    bot_mode: str = "polling"

    # ── Application port (injected by hosting platforms) ─────────────────────
    port: int = 8000

    # ── Computed helpers ──────────────────────────────────────────────────────
    @property
    def admin_ids(self) -> List[int]:
        """Parsed list of admin Telegram user IDs."""
        return [
            int(tid.strip())
            for tid in self.admin_telegram_ids.split(",")
            if tid.strip().isdigit()
        ]

    def is_admin(self, telegram_user_id: int) -> bool:
        """Return True if the given Telegram user ID is an authorised admin."""
        return telegram_user_id in self.admin_ids


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached Settings singleton.

    Using lru_cache means the .env file is only parsed once per process start.
    """
    return Settings()


# Convenience alias used throughout the project.
settings: Settings = get_settings()
