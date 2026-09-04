"""
app/database/indexes.py
=======================
Create all MongoDB indexes on startup.
Safe to call multiple times — MongoDB ignores existing indexes.
"""

from __future__ import annotations

import logging

from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database

logger = logging.getLogger(__name__)


def create_indexes(db: Database) -> None:
    """Create all required indexes. Call once at application startup."""

    # ── users ─────────────────────────────────────────────────────────────────
    db.users.create_index(
        [("telegramId", ASCENDING)],
        unique=True,
        name="users_telegramId_unique",
    )

    # ── movies ────────────────────────────────────────────────────────────────
    db.movies.create_index(
        [("isActive", ASCENDING)],
        name="movies_isActive",
    )
    db.movies.create_index(
        [("createdAt", ASCENDING)],
        name="movies_createdAt",
    )

    # ── orders ────────────────────────────────────────────────────────────────
    db.orders.create_index(
        [("orderCode", ASCENDING)],
        unique=True,
        name="orders_orderCode_unique",
    )
    db.orders.create_index(
        [("telegramUserId", ASCENDING)],
        name="orders_telegramUserId",
    )
    db.orders.create_index(
        [("status", ASCENDING)],
        name="orders_status",
    )
    db.orders.create_index(
        [("createdAt", DESCENDING)],
        name="orders_createdAt_desc",
    )
    # Compound index for admin pending order queries
    db.orders.create_index(
        [("status", ASCENDING), ("createdAt", DESCENDING)],
        name="orders_status_createdAt",
    )

    # ── sessions ──────────────────────────────────────────────────────────────
    db.sessions.create_index(
        [("telegramId", ASCENDING), ("botType", ASCENDING)],
        unique=True,
        name="sessions_telegramId_botType_unique",
    )
    # TTL index: auto-delete sessions after 24 hours of inactivity
    db.sessions.create_index(
        [("updatedAt", ASCENDING)],
        expireAfterSeconds=86400,
        name="sessions_ttl_24h",
    )

    # ── settings ──────────────────────────────────────────────────────────────
    db.settings.create_index(
        [("key", ASCENDING)],
        unique=True,
        name="settings_key_unique",
    )

    logger.info("All MongoDB indexes created/verified successfully.")
