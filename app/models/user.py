"""
app/models/user.py
─────────────────────────────────────────────────────────────────────────────
Customer / Telegram user profile model.

Data minimisation (req #35)
----------------------------
Only the fields needed for order verification and admin search are stored:
- telegramUserId  → primary key, permanent (req #4)
- username        → optional, for admin display and search
- firstName       → for personalised messages
- lastName        → optional

Fields deliberately NOT stored:
- Phone number     → Telegram does not expose this; we don't need it
- Email            → not required
- Location         → not required
- Profile photos   → not required

The `totalOrders` counter is a denormalised value updated atomically when an
order is created — avoids expensive COUNT queries on the orders collection
every time an admin views a customer profile.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class User(BaseModel):
    """
    Telegram user profile as stored in MongoDB.

    The `_id` field (MongoDB ObjectId) is managed by MongoDB and is not
    included here — documents are always looked up by `telegramUserId`.
    """

    telegramUserId: int = Field(
        ...,
        description="Telegram numeric user ID — permanent, never changes (req #4)",
    )
    username: Optional[str] = Field(
        default=None,
        description="Telegram @username — may be None or may change over time",
    )
    firstName: str = Field(
        ...,
        description="Telegram first name",
    )
    lastName: Optional[str] = Field(
        default=None,
        description="Telegram last name",
    )

    # Lifecycle timestamps (stored in UTC, displayed in configured TZ)
    firstSeenAt: datetime = Field(
        ...,
        description="UTC datetime when the user first interacted with the bot",
    )
    lastSeenAt: datetime = Field(
        ...,
        description="UTC datetime of the user's most recent interaction",
    )

    # Denormalised counter — updated atomically via $inc (req #19)
    totalOrders: int = Field(
        default=0,
        ge=0,
        description="Total number of orders ever placed by this user",
    )

    # ──────────────────────────────────────────────
    # Derived helpers (not stored in MongoDB)
    # ──────────────────────────────────────────────
    @property
    def display_name(self) -> str:
        """Human-readable name: '@username' if available, else 'First Last'."""
        if self.username:
            return f"@{self.username}"
        parts = [self.firstName]
        if self.lastName:
            parts.append(self.lastName)
        return " ".join(parts)

    @property
    def full_name(self) -> str:
        """Full name without @username prefix."""
        parts = [self.firstName]
        if self.lastName:
            parts.append(self.lastName)
        return " ".join(parts)
