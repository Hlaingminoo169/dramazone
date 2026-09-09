"""
app/database/connection.py
─────────────────────────────────────────────────────────────────────────────
Async MongoDB connection management using Motor.

Design
------
- Motor (AsyncIOMotorClient) provides non-blocking MongoDB access that
  integrates naturally with FastAPI's async request handlers.
- A single client instance is created at startup and shared across all
  requests (connection pooling).  Creating a new client per request would
  exhaust connections quickly.
- Pool size is tuned from config so the same code works on both Atlas (free
  tier) and a self-hosted VPS (req #41).
- `connect_db()` / `disconnect_db()` are called from FastAPI lifespan events.
- `get_database()` is a FastAPI dependency that returns the active DB handle.
- If MongoDB is unreachable at startup, the app logs a clear error and the
  health endpoint will return 503 — it does NOT expose connection details to
  callers (req #40).

Usage
-----
    # In FastAPI route / service:
    from fastapi import Depends
    from motor.motor_asyncio import AsyncIOMotorDatabase
    from app.database.connection import get_database

    async def my_route(db: AsyncIOMotorDatabase = Depends(get_database)):
        ...

    # Direct access (services called from within lifespan etc.):
    from app.database.connection import get_db
    db = get_db()
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

import certifi
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings

logger = logging.getLogger(__name__)

# Module-level state — intentionally not a global singleton class to keep
# the interface simple.  Only connection.py touches these.
_client: AsyncIOMotorClient | None = None
_database: AsyncIOMotorDatabase | None = None


async def connect_db() -> None:
    """
    Create the Motor client and verify connectivity.

    Called once from the FastAPI lifespan startup handler.
    Raises on failure so the app will not start with a broken DB connection.
    """
    global _client, _database  # noqa: PLW0603

    settings = get_settings()

    logger.info("Connecting to MongoDB (db=%s)…", settings.mongodb_db_name)

    _client = AsyncIOMotorClient(
        settings.mongodb_uri,
        minPoolSize=settings.mongodb_min_pool_size,
        maxPoolSize=settings.mongodb_max_pool_size,
        connectTimeoutMS=settings.mongodb_connect_timeout_ms,
        serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
        # Use certifi CA bundle — fixes TLS on most Python versions
        tlsCAFile=certifi.where(),
        # tlsInsecure: workaround for Python 3.14 strict TLS with Atlas.
        # Set MONGODB_TLS_INSECURE=true in .env ONLY for local dev.
        # On VPS with Python 3.11/3.12 leave this False.
        tlsInsecure=settings.mongodb_tls_insecure,
        # Ensure the driver uses UTC for all internal datetime handling
        tz_aware=True,
    )

    _database = _client[settings.mongodb_db_name]

    # Ping to verify the connection is actually usable.
    # serverSelectionTimeoutMS controls how long this waits.
    await _database.command("ping")

    logger.info(
        "MongoDB connected successfully (db=%s, pool=%d–%d)",
        settings.mongodb_db_name,
        settings.mongodb_min_pool_size,
        settings.mongodb_max_pool_size,
    )


async def disconnect_db() -> None:
    """
    Close the Motor client cleanly.

    Called from the FastAPI lifespan shutdown handler.
    Safe to call even if connect_db() was never called (e.g. test teardown).
    """
    global _client, _database  # noqa: PLW0603

    if _client is not None:
        _client.close()
        _client = None
        _database = None
        logger.info("MongoDB connection closed.")


def get_db() -> AsyncIOMotorDatabase:
    """
    Return the active database handle.

    Raises RuntimeError if called before connect_db() — this should never
    happen in normal operation because FastAPI lifespan guarantees ordering.
    """
    if _database is None:
        raise RuntimeError(
            "Database is not connected. "
            "Ensure connect_db() was called during application startup."
        )
    return _database


async def get_database() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """
    FastAPI dependency that yields the active database handle.

    Example
    -------
        from motor.motor_asyncio import AsyncIOMotorDatabase
        from app.database.connection import get_database
        from fastapi import Depends

        async def route(db: AsyncIOMotorDatabase = Depends(get_database)):
            users = await db[USERS].find_one({"telegramUserId": 12345})
    """
    yield get_db()
