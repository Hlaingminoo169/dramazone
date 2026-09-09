"""
app/services/user_service.py
─────────────────────────────────────────────────────────────────────────────
Customer user profile service.

Upserts a Telegram user profile on every interaction.
Only stores fields required for order verification and admin search (req #35).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from telegram import User as TelegramUser

from app.database.collections import USERS

logger = logging.getLogger(__name__)


async def upsert_user(db: AsyncIOMotorDatabase, telegram_user: TelegramUser) -> dict:
    """
    Create or update a customer profile.

    - On first visit: inserts with firstSeenAt, totalOrders=0
    - On subsequent visits: updates username/name/lastSeenAt only
    """
    now = datetime.now(timezone.utc)

    doc = await db[USERS].find_one_and_update(
        {"telegramUserId": telegram_user.id},
        {
            "$set": {
                "username": telegram_user.username,
                "firstName": telegram_user.first_name,
                "lastName": telegram_user.last_name,
                "lastSeenAt": now,
            },
            "$setOnInsert": {
                "telegramUserId": telegram_user.id,
                "firstSeenAt": now,
                "totalOrders": 0,
            },
        },
        upsert=True,
        return_document=True,
    )
    return doc
