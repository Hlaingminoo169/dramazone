"""
app/services/rate_limit_service.py
─────────────────────────────────────────────────────────────────────────────
Lightweight MongoDB TTL-based rate limiter (req #2).

No Redis required. Each rate-limit window is a MongoDB document with a TTL
index that auto-deletes it when the window expires.

Fail-safe design (req #2):
  If MongoDB has an error, the limiter ALLOWS the action (fail open) and logs
  the error. A broken rate limiter should not make the bot unusable.

Key format: "{action}:{identifier}"
  e.g. "start:12345678", "callback:12345678", "order:12345678"
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import get_settings
from app.database.collections import RATE_LIMITS

logger = logging.getLogger(__name__)


async def check_and_increment(
    db: AsyncIOMotorDatabase,
    action: str,
    identifier: int | str,
    limit: int,
    window_sec: int,
) -> bool:
    """
    Check whether the action is within rate limit and increment the counter.

    Returns
    -------
    True  → action is allowed (count is within limit)
    False → rate limit exceeded

    The function is atomic via MongoDB upsert:
    - If no document exists for this key → create with count=1
    - If document exists → increment count
    The TTL index auto-deletes the document when the window expires.
    """
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return True

    key = f"{action}:{identifier}"

    try:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=window_sec)

        result = await db[RATE_LIMITS].find_one_and_update(
            {"key": key},
            {
                "$inc": {"count": 1},
                "$setOnInsert": {
                    "key": key,
                    "windowStart": now,
                    "expiresAt": expires_at,
                },
            },
            upsert=True,
            return_document=True,
        )

        count = result.get("count", 1)
        allowed = count <= limit

        if not allowed:
            logger.info("Rate limit hit: key=%s count=%d limit=%d", key, count, limit)

        return allowed

    except Exception:
        # Fail open — log but do not block the user (req #2 fail-safe)
        logger.exception("Rate limiter error for key=%s — allowing action", key)
        return True
