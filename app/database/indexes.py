"""
app/database/indexes.py
─────────────────────────────────────────────────────────────────────────────
MongoDB index definitions for all collections.

Why indexes matter here
-----------------------
Indexes are created at application startup (idempotent — MongoDB will not
recreate an existing identical index).  Defining them in code rather than
relying on manual Atlas UI work means:

1. Every environment (dev, staging, prod, VPS) has exactly the same indexes.
2. Indexes are version-controlled alongside the code that needs them.
3. New team members / VPS deployments get the correct indexes automatically.

Index design rationale (req #19, #20)
--------------------------------------
Indexes are chosen to support the specific queries used by:
- Admin pending/all-orders views (status, createdAt)
- Per-customer order history (telegramUserId)
- Sales reporting by date range (status + createdAt compound)
- Order lookup by code (unique, orderCode)
- Payment method reporting (paymentMethod + status)
- Admin search (orderCode, telegramUserId, username)
- Rate limiting with auto-expiry (TTL on expiresAt)
- Session recovery with auto-expiry (TTL on expiresAt)
- Admin audit trail lookup (adminTelegramId, orderCode)
- Movie activity filter (isActive)

Indexes NOT created
-------------------
- No wildcard / text indexes — they consume significant storage and RAM.
  Full-text search is not a core requirement in v1.
- No excessive compound indexes — each is justified by a real query pattern.

Usage
-----
    from app.database.indexes import create_indexes
    await create_indexes(db)
"""

from __future__ import annotations

import logging

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.database.collections import (
    AUDIT_LOGS,
    MOVIES,
    ORDERS,
    RATE_LIMITS,
    SESSIONS,
    USERS,
)

logger = logging.getLogger(__name__)


async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    """
    Create all required indexes across every collection.

    This function is idempotent — safe to call on every app startup.
    MongoDB will skip creation if an identical index already exists.
    """
    logger.info("Creating/verifying MongoDB indexes…")

    await _create_orders_indexes(db)
    await _create_users_indexes(db)
    await _create_sessions_indexes(db)
    await _create_rate_limits_indexes(db)
    await _create_audit_logs_indexes(db)
    await _create_movies_indexes(db)

    logger.info("All MongoDB indexes are in place.")


# ──────────────────────────────────────────────
# ORDERS (req #20)
# Central collection — most query patterns live here
# ──────────────────────────────────────────────
async def _create_orders_indexes(db: AsyncIOMotorDatabase) -> None:
    indexes = [
        # Unique order code lookup — for admin search and customer status check
        IndexModel(
            [("orderCode", ASCENDING)],
            unique=True,
            name="orderCode_unique",
        ),

        # Per-customer order history (req #34, #35)
        IndexModel(
            [("telegramUserId", ASCENDING)],
            name="telegramUserId_asc",
        ),

        # Status filter — pending orders view (req #9)
        IndexModel(
            [("status", ASCENDING)],
            name="status_asc",
        ),

        # Time-range reporting queries (req #10–#14, #37)
        IndexModel(
            [("createdAt", DESCENDING)],
            name="createdAt_desc",
        ),

        # Pending orders sorted newest first (req #9)
        # Compound: status lookup + newest-first sort in a single index scan
        IndexModel(
            [("status", ASCENDING), ("createdAt", DESCENDING)],
            name="status_createdAt_compound",
        ),

        # Payment method reporting — approved orders per payment method (req #17)
        IndexModel(
            [("paymentMethod", ASCENDING), ("status", ASCENDING)],
            name="paymentMethod_status_compound",
        ),

        # Date-range revenue reporting — approved orders within time window
        # Supports: {status: "APPROVED", createdAt: {$gte: ..., $lte: ...}}
        IndexModel(
            [("status", ASCENDING), ("createdAt", ASCENDING)],
            name="status_createdAt_asc_compound",
        ),

        # Admin search by username (req #34)
        IndexModel(
            [("telegramUsername", ASCENDING)],
            sparse=True,  # sparse because username can be null
            name="telegramUsername_sparse",
        ),
    ]

    await db[ORDERS].create_indexes(indexes)
    logger.debug("orders indexes created/verified (%d indexes)", len(indexes))


# ──────────────────────────────────────────────
# USERS (req #34, #35)
# ──────────────────────────────────────────────
async def _create_users_indexes(db: AsyncIOMotorDatabase) -> None:
    indexes = [
        # Primary lookup — always by Telegram user ID (req #4)
        IndexModel(
            [("telegramUserId", ASCENDING)],
            unique=True,
            name="telegramUserId_unique",
        ),

        # Admin search by username (sparse — username is optional on Telegram)
        IndexModel(
            [("username", ASCENDING)],
            sparse=True,
            name="username_sparse",
        ),
    ]

    await db[USERS].create_indexes(indexes)
    logger.debug("users indexes created/verified (%d indexes)", len(indexes))


# ──────────────────────────────────────────────
# SESSIONS (req #30, #31)
# TTL index auto-deletes expired sessions — no cron job needed
# ──────────────────────────────────────────────
async def _create_sessions_indexes(db: AsyncIOMotorDatabase) -> None:
    indexes = [
        # One active session per Telegram user
        IndexModel(
            [("telegramUserId", ASCENDING)],
            unique=True,
            name="telegramUserId_unique",
        ),

        # TTL: MongoDB auto-deletes documents when expiresAt < current time.
        # The `expireAfterSeconds=0` means "expire at the datetime in expiresAt".
        # The actual expiry time is controlled by the application when setting
        # the expiresAt field (SESSION_EXPIRY_HOURS from config).
        IndexModel(
            [("expiresAt", ASCENDING)],
            expireAfterSeconds=0,
            name="expiresAt_ttl",
        ),
    ]

    await db[SESSIONS].create_indexes(indexes)
    logger.debug("sessions indexes created/verified (%d indexes)", len(indexes))


# ──────────────────────────────────────────────
# RATE LIMITS (req #2)
# TTL index auto-cleans expired rate limit windows
# ──────────────────────────────────────────────
async def _create_rate_limits_indexes(db: AsyncIOMotorDatabase) -> None:
    indexes = [
        # Composite key lookup: "rl:{action}:{telegramUserId}"
        IndexModel(
            [("key", ASCENDING)],
            unique=True,
            name="key_unique",
        ),

        # TTL: auto-expire rate limit windows after the configured period
        # expiresAt is set to windowStart + RATE_LIMIT_WINDOW_SECONDS
        IndexModel(
            [("expiresAt", ASCENDING)],
            expireAfterSeconds=0,
            name="expiresAt_ttl",
        ),
    ]

    await db[RATE_LIMITS].create_indexes(indexes)
    logger.debug("rate_limits indexes created/verified (%d indexes)", len(indexes))


# ──────────────────────────────────────────────
# AUDIT LOGS (req #5)
# ──────────────────────────────────────────────
async def _create_audit_logs_indexes(db: AsyncIOMotorDatabase) -> None:
    indexes = [
        # Per-admin activity trail, newest first
        IndexModel(
            [("adminTelegramId", ASCENDING), ("timestamp", DESCENDING)],
            name="adminTelegramId_timestamp_compound",
        ),

        # Lookup all audit events for a specific order (req #38)
        IndexModel(
            [("orderCode", ASCENDING)],
            sparse=True,  # sparse — not all audit events relate to orders
            name="orderCode_sparse",
        ),

        # General time-based audit queries
        IndexModel(
            [("timestamp", DESCENDING)],
            name="timestamp_desc",
        ),
    ]

    await db[AUDIT_LOGS].create_indexes(indexes)
    logger.debug("audit_logs indexes created/verified (%d indexes)", len(indexes))


# ──────────────────────────────────────────────
# MOVIES (req #15)
# ──────────────────────────────────────────────
async def _create_movies_indexes(db: AsyncIOMotorDatabase) -> None:
    indexes = [
        # Filter to active movies only (most queries exclude disabled movies)
        IndexModel(
            [("isActive", ASCENDING)],
            name="isActive_asc",
        ),
    ]

    await db[MOVIES].create_indexes(indexes)
    logger.debug("movies indexes created/verified (%d indexes)", len(indexes))
