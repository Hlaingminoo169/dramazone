"""
app/config.py
─────────────────────────────────────────────────────────────────────────────
Centralised, type-safe application configuration.

All values are loaded from environment variables (or a .env file in
development).  Defaults are provided only where a sensible, safe fallback
exists.  Required values with no default will raise a clear error at startup
if they are missing — fail-fast is preferable to silent misconfiguration.

Usage
-----
    from app.config import get_settings

    settings = get_settings()
    print(settings.mongodb_uri)

Notes
-----
- `get_settings()` is cached via `@lru_cache` so the Settings object is
  instantiated only once per process lifetime.
- Admin IDs are stored as a comma-separated string in the environment and
  parsed into a `List[int]` here (req #4).  Never rely on Telegram usernames.
- All rate-limit thresholds are configurable from the environment (req #2).
- Pricing tiers live here so they can be updated without code changes (req #16).
- Timezone is configurable; defaults to Asia/Yangon (req #37).
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",          # silently ignore unknown env vars
    )

    # ──────────────────────────────────────────────
    # APPLICATION
    # ──────────────────────────────────────────────
    app_name: str = Field(default="DramaZone VIP Bot")
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")

    # ──────────────────────────────────────────────
    # MONGODB
    # ──────────────────────────────────────────────
    mongodb_uri: str = Field(
        ...,
        description="MongoDB connection string (Atlas URI or self-hosted)",
    )
    mongodb_db_name: str = Field(default="dramazone")
    mongodb_min_pool_size: int = Field(default=2)
    mongodb_max_pool_size: int = Field(default=10)
    mongodb_connect_timeout_ms: int = Field(default=5000)
    mongodb_server_selection_timeout_ms: int = Field(default=5000)
    # Set True only when your Python/OpenSSL version is incompatible with Atlas TLS.
    # Python 3.14 pre-release has stricter TLS that breaks Atlas SSL handshake.
    # On VPS with Python 3.11/3.12 this should be False (default).
    mongodb_tls_insecure: bool = Field(
        default=False,
        description="Skip TLS certificate verification (dev only, Python 3.14 workaround)",
    )

    # ──────────────────────────────────────────────
    # TELEGRAM BOTS
    # ──────────────────────────────────────────────
    customer_bot_token: str = Field(default="")
    admin_bot_token: str = Field(default="")
    webhook_secret: str = Field(default="")
    webhook_base_url: str = Field(default="")
    # "polling"  → local dev, no HTTPS needed
    # "webhook"  → production, requires WEBHOOK_BASE_URL + WEBHOOK_SECRET
    bot_mode: str = Field(default="polling")

    # ──────────────────────────────────────────────
    # ADMIN ACCESS (req #4)
    # Stored as comma-separated string in env; parsed to List[int] here.
    # Numeric Telegram user IDs only — usernames can change.
    # ──────────────────────────────────────────────
    admin_telegram_ids: str = Field(
        default="1673861706,1655754454",
        description="Comma-separated Telegram numeric user IDs for admins",
    )

    @field_validator("admin_telegram_ids", mode="before")
    @classmethod
    def validate_admin_ids_string(cls, v: str) -> str:
        """Ensure the raw string parses cleanly to integers."""
        try:
            for part in str(v).split(","):
                int(part.strip())
        except ValueError as exc:
            raise ValueError(
                "ADMIN_TELEGRAM_IDS must be comma-separated integers "
                f"(e.g. 1673861706,1655754454). Got: {v!r}"
            ) from exc
        return v

    @property
    def admin_ids(self) -> List[int]:
        """Parsed list of admin Telegram user IDs."""
        return [int(x.strip()) for x in self.admin_telegram_ids.split(",") if x.strip()]

    # ──────────────────────────────────────────────
    # RATE LIMITING (req #2)
    # MongoDB TTL-backed — no Redis required.
    # ──────────────────────────────────────────────
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_window_seconds: int = Field(default=60)
    rate_limit_max_requests: int = Field(default=30)
    order_rate_limit: int = Field(
        default=5,
        description="Max orders a user can create per hour",
    )
    screenshot_rate_limit: int = Field(
        default=3,
        description="Max screenshots a user can submit per order",
    )
    start_cooldown_seconds: int = Field(
        default=10,
        description="Cooldown between /start commands from the same user",
    )

    # ──────────────────────────────────────────────
    # SESSION (req #30, #31)
    # ──────────────────────────────────────────────
    session_expiry_hours: int = Field(
        default=24,
        description="Hours before an incomplete session is auto-expired",
    )

    # ──────────────────────────────────────────────
    # REPORTING / TIMEZONE (req #37)
    # ──────────────────────────────────────────────
    report_timezone: str = Field(
        default="Asia/Yangon",
        description="pytz timezone name for all displayed timestamps/reports",
    )

    # ──────────────────────────────────────────────
    # PAYMENT ACCOUNTS (req #24)
    # ──────────────────────────────────────────────
    payment_ayapay_name: str = Field(default="")
    payment_ayapay_phone: str = Field(default="")
    payment_uabpay_name: str = Field(default="")
    payment_uabpay_phone: str = Field(default="")
    payment_kpay_name: str = Field(default="")
    payment_kpay_phone: str = Field(default="")
    payment_wave_name: str = Field(default="")
    payment_wave_phone: str = Field(default="")

    # ──────────────────────────────────────────────
    # PRICING (req #16 — package tiers)
    # Prices in MMK.  Configurable without code changes.
    # Only 3 tiers: 1, 3, 5 movies.
    # ──────────────────────────────────────────────
    price_1_movie: int = Field(default=1500)
    price_3_movies: int = Field(default=3500)
    price_5_movies: int = Field(default=5000)

    @property
    def package_prices(self) -> dict[int, int]:
        """Map of {movie_count: price_mmk} for all available package tiers."""
        return {
            1: self.price_1_movie,
            3: self.price_3_movies,
            5: self.price_5_movies,
        }

    @property
    def available_package_sizes(self) -> list[int]:
        """Ordered list of available package sizes."""
        return [1, 3, 5]

    # ──────────────────────────────────────────────
    # SECURITY MISC (req #1)
    # ──────────────────────────────────────────────
    max_request_size_bytes: int = Field(
        default=10 * 1024 * 1024,   # 10 MB
        description="Maximum allowed webhook request body size in bytes",
    )

    # ──────────────────────────────────────────────
    # DERIVED HELPERS
    # ──────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the singleton Settings instance.

    Cached with lru_cache so the .env file is read only once per process.
    In tests, call get_settings.cache_clear() before patching env vars.
    """
    return Settings()  # type: ignore
