"""
app/services/session_service.py
─────────────────────────────────────────────────────────────────────────────
MongoDB-backed session service.

Provides get / update / clear operations on the sessions collection.
TTL is reset on every update so active sessions stay alive.
Expired sessions are auto-deleted by MongoDB TTL index.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import get_settings
from app.database.collections import SESSIONS
from app.models.session import SessionState

logger = logging.getLogger(__name__)

# Default IDLE session returned when no document exists
_DEFAULT_SESSION: dict = {
    "state": SessionState.IDLE,
    "packageSize": None,
    "selectedMovieIds": [],
    "pendingOrderCode": None,
    "lastBotMessageId": None,
}


async def get_session(db: AsyncIOMotorDatabase, user_id: int) -> dict:
    """
    Return the user's active session document.
    If no session exists, returns a default IDLE dict (not saved to DB yet).
    """
    doc = await db[SESSIONS].find_one({"telegramUserId": user_id})
    if not doc:
        return {**_DEFAULT_SESSION, "telegramUserId": user_id}
    return doc


async def update_session(
    db: AsyncIOMotorDatabase,
    user_id: int,
    **fields,
) -> None:
    """
    Upsert session fields for the given user.
    Always resets the TTL expiry so active sessions don't expire mid-flow.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=settings.session_expiry_hours)

    await db[SESSIONS].update_one(
        {"telegramUserId": user_id},
        {
            "$set": {
                **fields,
                "telegramUserId": user_id,
                "updatedAt": now,
                "expiresAt": expires_at,
            }
        },
        upsert=True,
    )


async def clear_session(db: AsyncIOMotorDatabase, user_id: int) -> None:
    """Reset session to IDLE state, clearing all in-progress order data."""
    await update_session(
        db,
        user_id,
        state=SessionState.IDLE,
        packageSize=None,
        selectedMovieIds=[],
        pendingOrderCode=None,
    )


async def get_state(db: AsyncIOMotorDatabase, user_id: int) -> SessionState:
    """Convenience: return just the current session state."""
    session = await get_session(db, user_id)
    return SessionState(session.get("state", SessionState.IDLE))
