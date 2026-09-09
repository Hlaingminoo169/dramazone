"""
app/models/session.py
─────────────────────────────────────────────────────────────────────────────
MongoDB-backed user session model for conversation state recovery.

Why MongoDB sessions? (req #30)
---------------------------------
Telegram bots are stateless by nature — when a user closes the app and
returns later, the bot has no memory of what they were doing.  In-memory
state (Python dicts, class attributes) is lost on restart and doesn't
survive VPS migrations.

Solution: store the current conversation state in MongoDB.  When a user
sends any message, the bot loads their session and resumes from where they
left off.  This works across restarts, deployments, and VPS migrations.

Session expiry (req #31)
--------------------------
Sessions have an `expiresAt` datetime field.  A MongoDB TTL index on this
field causes MongoDB to automatically delete expired documents — no cron
job or background task is needed.

Only incomplete/active sessions are stored here.  Completed order history
lives in the `orders` collection and is never deleted by this TTL.

Session uniqueness
-------------------
One session per Telegram user (unique index on `telegramUserId`).  If a
user starts a new order while one is pending, the previous session is
replaced via upsert.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class SessionState(str, Enum):
    """
    Active conversation states.

    Maps to the order progress flow shown to customers (req #22):

      IDLE                → no active order
      SELECTING_PACKAGE   → customer is choosing a package tier (1/3/5 movies)
      SELECTING_MOVIES    → customer is choosing movies from the catalog
      CONFIRMING_ORDER    → showing order summary, awaiting confirmation
      SELECTING_PAYMENT   → customer is choosing a payment method
      AWAITING_SCREENSHOT → waiting for customer to send payment photo
    """

    IDLE = "IDLE"
    SELECTING_PACKAGE = "SELECTING_PACKAGE"
    SELECTING_MOVIES = "SELECTING_MOVIES"
    CONFIRMING_ORDER = "CONFIRMING_ORDER"
    SELECTING_PAYMENT = "SELECTING_PAYMENT"
    AWAITING_SCREENSHOT = "AWAITING_SCREENSHOT"


class Session(BaseModel):
    """
    Active conversation session as stored in MongoDB.

    Upserted on every state change; auto-deleted by TTL index on `expiresAt`.
    """

    telegramUserId: int = Field(
        ...,
        description="Customer's Telegram user ID — unique index (one session per user)",
    )
    state: SessionState = Field(
        default=SessionState.IDLE,
        description="Current conversation state",
    )
    packageSize: Optional[int] = Field(
        default=None,
        description="Chosen package size: 1, 3, or 5",
    )
    selectedMovieIds: List[str] = Field(
        default_factory=list,
        description="Movie _ids the customer has selected so far in this session",
    )

    # Link to an in-progress order (set when order document is created)
    pendingOrderCode: Optional[str] = Field(
        default=None,
        description=(
            "orderCode of the in-progress order, if one exists. "
            "None if the user is still in the movie selection phase."
        ),
    )

    # Message ID of the most recent bot message — used to edit instead of
    # sending new messages (cleaner UX, avoids message floods)
    lastBotMessageId: Optional[int] = Field(
        default=None,
        description="Telegram message ID of the most recent bot message to this user",
    )

    # Lifecycle
    expiresAt: datetime = Field(
        ...,
        description=(
            "UTC datetime after which this session is considered expired. "
            "MongoDB TTL index auto-deletes documents past this time (req #31)."
        ),
    )
    updatedAt: datetime = Field(
        ...,
        description="UTC datetime of the most recent session update",
    )
