"""
app/database/indexes.py

MongoDB index definitions.

All indexes are created idempotently — calling ensure_indexes() multiple
times is safe (PyMongo skips creation if the index already exists).

Call ensure_indexes() once after connecting, during application startup.
"""
from __future__ import annotations

import logging

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import OperationFailure

from app.database.mongodb import get_db

logger = logging.getLogger(__name__)


def ensure_indexes() -> None:
    """
    Create all required indexes on every collection.

    Idempotent — safe to call on every startup.
    Logs a warning but does NOT raise if index creation fails, so a
    permissions issue does not prevent the application from starting.
    """
    db = get_db()
    _create_user_indexes(db)
    _create_movie_indexes(db)
    _create_order_indexes(db)
    _create_session_indexes(db)
    _create_settings_indexes(db)
    logger.info("MongoDB indexes verified.")


# ── Per-collection helpers ───────────────────────────────────────────────────

def _create_user_indexes(db) -> None:
    try:
        db["users"].create_index(
            [("telegramId", ASCENDING)],
            unique=True,
            name="ix_users_telegramId_unique",
        )
        logger.debug("users indexes OK")
    except OperationFailure as exc:
        logger.warning("Could not create users indexes: %s", exc)


def _create_movie_indexes(db) -> None:
    try:
        db["movies"].create_index(
            [("isActive", ASCENDING)],
            name="ix_movies_isActive",
        )
        logger.debug("movies indexes OK")
    except OperationFailure as exc:
        logger.warning("Could not create movies indexes: %s", exc)


def _create_order_indexes(db) -> None:
    try:
        col = db["orders"]

        col.create_index(
            [("orderCode", ASCENDING)],
            unique=True,
            name="ix_orders_orderCode_unique",
        )
        col.create_index(
            [("telegramUserId", ASCENDING)],
            name="ix_orders_telegramUserId",
        )
        col.create_index(
            [("status", ASCENDING)],
            name="ix_orders_status",
        )
        col.create_index(
            [("createdAt", DESCENDING)],
            name="ix_orders_createdAt_desc",
        )
        # Compound index for fetching a user's orders sorted by date (order history)
        col.create_index(
            [("telegramUserId", ASCENDING), ("createdAt", DESCENDING)],
            name="ix_orders_userId_createdAt",
        )
        logger.debug("orders indexes OK")
    except OperationFailure as exc:
        logger.warning("Could not create orders indexes: %s", exc)


def _create_session_indexes(db) -> None:
    try:
        col = db["sessions"]

        # Composite unique index: one session per (user, bot)
        col.create_index(
            [("telegramId", ASCENDING), ("botType", ASCENDING)],
            unique=True,
            name="ix_sessions_telegramId_botType_unique",
        )
        # TTL index: automatically expire stale sessions after 24 hours
        # of inactivity.  MongoDB removes the document when
        #   updatedAt + 86400 seconds < now
        col.create_index(
            [("updatedAt", ASCENDING)],
            expireAfterSeconds=86_400,  # 24 hours
            name="ix_sessions_updatedAt_ttl",
        )
        logger.debug("sessions indexes OK")
    except OperationFailure as exc:
        logger.warning("Could not create sessions indexes: %s", exc)


def _create_settings_indexes(db) -> None:
    try:
        db["settings"].create_index(
            [("key", ASCENDING)],
            unique=True,
            name="ix_settings_key_unique",
        )
        logger.debug("settings indexes OK")
    except OperationFailure as exc:
        logger.warning("Could not create settings indexes: %s", exc)
