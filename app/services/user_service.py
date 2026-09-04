"""
app/services/user_service.py
=============================
User upsert and lookup operations.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from pymongo.database import Database
from telegram import User as TelegramUser

logger = logging.getLogger(__name__)


def upsert_user(db: Database, tg_user: TelegramUser) -> None:
    """
    Create or update a user record from a Telegram User object.
    Only updates mutable fields (username, name) — never overwrites createdAt.
    """
    now = datetime.now(timezone.utc)
    db.users.update_one(
        {"telegramId": tg_user.id},
        {
            "$set": {
                "username": tg_user.username or "",
                "firstName": tg_user.first_name or "",
                "lastName": tg_user.last_name or "",
                "updatedAt": now,
            },
            "$setOnInsert": {
                "telegramId": tg_user.id,
                "createdAt": now,
            },
        },
        upsert=True,
    )


def get_user(db: Database, telegram_id: int) -> dict | None:
    """Return a user document by Telegram ID."""
    return db.users.find_one({"telegramId": telegram_id})
