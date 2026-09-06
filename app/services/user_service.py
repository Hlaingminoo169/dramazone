"""
app/services/user_service.py

Customer user management.

Upserts user profile on every /start interaction.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from pymongo import ReturnDocument
from telegram import User as TelegramUser

from app.database.mongodb import get_collection
from app.types import Collection

logger = logging.getLogger(__name__)


def upsert_user(tg_user: TelegramUser) -> dict:
    """
    Create or update a user document from a Telegram User object.

    Always updates `updatedAt`. Sets `createdAt` only on first insert.
    """
    col = get_collection(Collection.USERS)
    now = datetime.now(timezone.utc)
    doc = col.find_one_and_update(
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
        return_document=ReturnDocument.AFTER,
    )
    return doc


def get_user(telegram_id: int) -> Optional[dict]:
    """Return a user by Telegram ID, or None."""
    col = get_collection(Collection.USERS)
    return col.find_one({"telegramId": telegram_id})
