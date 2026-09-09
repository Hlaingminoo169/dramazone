"""
app/models/rate_limit.py
─────────────────────────────────────────────────────────────────────────────
MongoDB-backed rate limit tracker model.

Architecture (req #2)
-----------------------
Rate limiting is implemented using MongoDB TTL documents — no Redis or
external service required.  This keeps the infrastructure footprint small
and the system VPS-portable.

How it works
-------------
Each rate-limit "window" is a document in the `rate_limits` collection:

  key        → composite string: "{action}:{telegramUserId}"
               e.g. "start:12345678", "callback:12345678", "order:12345678"
  count      → number of actions in the current window
  windowStart → UTC start of the current window
  expiresAt  → windowStart + window_duration
               MongoDB TTL index auto-deletes the document after this time

To check/increment a rate limit (pseudo-code):
  1. Try to find the document by key
  2. If not found → create it (count=1, fresh window)
  3. If found and count < limit → increment count atomically ($inc)
  4. If found and count >= limit → reject the action

MongoDB's `findOneAndUpdate` with `upsert=True` ensures this is atomic —
no race conditions even under concurrent requests.

Failure safety (req #2 — "fail safely")
-----------------------------------------
If the rate limiter encounters a MongoDB error, it should LOG the error
and ALLOW the action (fail open) rather than blocking all users.
A broken rate limiter should not make the bot unusable.

Key format convention
----------------------
  General commands:    "cmd:{user_id}"
  /start command:      "start:{user_id}"
  Callback queries:    "callback:{user_id}"
  Order creation:      "order:{user_id}"
  Screenshot upload:   "screenshot:{order_code}:{user_id}"
  Admin actions:       "admin:{user_id}"
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class RateLimitAction(str, Enum):
    """
    Rate limit action types — used to construct the composite key.

    Each action can have its own limit configured independently (req #2).
    """

    START = "start"
    CALLBACK = "callback"
    ORDER = "order"
    SCREENSHOT = "screenshot"
    ADMIN = "admin"
    COMMAND = "cmd"


class RateLimitEntry(BaseModel):
    """
    Rate limit window document as stored in MongoDB.

    Auto-deleted by TTL index when `expiresAt` is reached.
    The service layer uses atomic upsert operations to update these documents.
    """

    key: str = Field(
        ...,
        description=(
            "Composite rate limit key: '{action}:{identifier}'. "
            "Example: 'start:12345678' or 'screenshot:DZ-20260909-AB12:12345678'"
        ),
    )
    count: int = Field(
        default=1,
        ge=1,
        description="Number of actions taken in the current window",
    )
    windowStart: datetime = Field(
        ...,
        description="UTC start of the current rate limit window",
    )
    expiresAt: datetime = Field(
        ...,
        description=(
            "UTC datetime when this window expires. "
            "MongoDB TTL index auto-deletes the document at this time."
        ),
    )

    @staticmethod
    def build_key(action: RateLimitAction | str, *identifiers: str | int) -> str:
        """
        Construct a rate limit key from an action and one or more identifiers.

        Examples
        --------
            RateLimitEntry.build_key(RateLimitAction.START, 12345678)
            → "start:12345678"

            RateLimitEntry.build_key(RateLimitAction.SCREENSHOT, "DZ-20260909-AB12", 12345678)
            → "screenshot:DZ-20260909-AB12:12345678"
        """
        action_str = action.value if isinstance(action, RateLimitAction) else action
        parts = [action_str] + [str(i) for i in identifiers]
        return ":".join(parts)
