"""
app/services/session_service.py

MongoDB-backed session management.

Because FastAPI webhooks are stateless (requests may hit any instance),
user session state MUST be stored in MongoDB — NOT in Python dicts.

Sessions expire automatically after 24 hours via a MongoDB TTL index
(see app/database/indexes.py).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pymongo import ReturnDocument

from app.database.mongodb import get_collection
from app.types import BotType, Collection

logger = logging.getLogger(__name__)


def get_session(telegram_id: int, bot_type: str) -> Optional[dict]:
    """Return the current session document for a user, or None."""
    col = get_collection(Collection.SESSIONS)
    return col.find_one({"telegramId": telegram_id, "botType": bot_type})


def set_session(
    telegram_id: int,
    bot_type: str,
    state: str,
    data: Optional[Dict[str, Any]] = None,
) -> dict:
    """
    Upsert a session for the given user.

    Always updates `updatedAt` so the TTL index resets the 24-hour clock.
    """
    col = get_collection(Collection.SESSIONS)
    now = datetime.now(timezone.utc)
    doc = col.find_one_and_update(
        {"telegramId": telegram_id, "botType": bot_type},
        {
            "$set": {
                "state": state,
                "data": data or {},
                "updatedAt": now,
            },
            "$setOnInsert": {
                "telegramId": telegram_id,
                "botType": bot_type,
                "createdAt": now,
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return doc


def update_session_data(
    telegram_id: int,
    bot_type: str,
    data: Dict[str, Any],
) -> Optional[dict]:
    """
    Merge new key/value pairs into the session's `data` field
    without changing the current state.
    """
    col = get_collection(Collection.SESSIONS)
    now = datetime.now(timezone.utc)
    # Build a $set of "data.<key>" paths to merge without overwriting other keys.
    set_fields: Dict[str, Any] = {"updatedAt": now}
    for k, v in data.items():
        set_fields[f"data.{k}"] = v

    return col.find_one_and_update(
        {"telegramId": telegram_id, "botType": bot_type},
        {"$set": set_fields},
        return_document=ReturnDocument.AFTER,
    )


def clear_session(telegram_id: int, bot_type: str) -> None:
    """Delete the session document for the given user."""
    col = get_collection(Collection.SESSIONS)
    col.delete_one({"telegramId": telegram_id, "botType": bot_type})


def get_session_state(telegram_id: int, bot_type: str) -> Optional[str]:
    """Shortcut — return just the state string."""
    session = get_session(telegram_id, bot_type)
    return session.get("state") if session else None


def get_session_data(telegram_id: int, bot_type: str) -> Dict[str, Any]:
    """Shortcut — return just the data dict (empty dict if no session)."""
    session = get_session(telegram_id, bot_type)
    return session.get("data", {}) if session else {}
