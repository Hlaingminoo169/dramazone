"""
app/services/session_service.py
================================
MongoDB-backed session management.
No in-memory state — safe for stateless/serverless hosting.

Session document structure:
{
    telegramId: int,
    botType:    "CUSTOMER" | "ADMIN",
    state:      str,       # CustomerState or AdminState value
    data:       dict,      # arbitrary session payload
    updatedAt:  datetime,  # TTL field — auto-deleted after 24h
}
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pymongo.database import Database

from app.types import BotType

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_session(db: Database, telegram_id: int, bot_type: BotType) -> dict:
    """
    Return the session document for a user, or a blank session if none exists.
    Never returns None — callers always get a usable dict.
    """
    doc = db.sessions.find_one(
        {"telegramId": telegram_id, "botType": bot_type.value}
    )
    if doc:
        return doc
    return {
        "telegramId": telegram_id,
        "botType": bot_type.value,
        "state": "IDLE",
        "data": {},
        "updatedAt": _now(),
    }


def set_session(
    db: Database,
    telegram_id: int,
    bot_type: BotType,
    state: str,
    data: dict[str, Any] | None = None,
) -> None:
    """
    Upsert the session for a user. Always refreshes updatedAt (TTL reset).
    """
    db.sessions.update_one(
        {"telegramId": telegram_id, "botType": bot_type.value},
        {
            "$set": {
                "state": state,
                "data": data or {},
                "updatedAt": _now(),
            }
        },
        upsert=True,
    )


def clear_session(db: Database, telegram_id: int, bot_type: BotType) -> None:
    """Reset a user's session to IDLE with empty data."""
    set_session(db, telegram_id, bot_type, state="IDLE", data={})


def update_session_data(
    db: Database,
    telegram_id: int,
    bot_type: BotType,
    data: dict[str, Any],
) -> None:
    """
    Merge new data into an existing session without changing the state.
    """
    db.sessions.update_one(
        {"telegramId": telegram_id, "botType": bot_type.value},
        {
            "$set": {
                "updatedAt": _now(),
            },
            "$set": {"data": data},
        },
        upsert=True,
    )
