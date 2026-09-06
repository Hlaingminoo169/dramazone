"""
app/database/mongodb.py

MongoDB Atlas connection management.

Design decisions:
- A single MongoClient is created once at application startup and reused
  across all requests (thread-safe for PyMongo).
- The client is stored as a module-level singleton; FastAPI lifespan events
  call connect() on startup and close() on shutdown.
- No connection is created per request.
- The MONGODB_URI and credentials are read from settings; never printed.
"""
from __future__ import annotations

import logging
from typing import Optional

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ConfigurationError, ServerSelectionTimeoutError

from app.config import settings

logger = logging.getLogger(__name__)

# ── Module-level singletons ──────────────────────────────────────────────────
_client: Optional[MongoClient] = None
_database: Optional[Database] = None


def connect() -> None:
    """
    Initialise the MongoDB client and validate the connection.

    Called once during application startup (FastAPI lifespan).
    Raises RuntimeError if the connection cannot be established so the
    application fails fast rather than serving broken requests.
    """
    global _client, _database

    if not settings.mongodb_uri:
        raise RuntimeError(
            "MONGODB_URI is not set. "
            "Add it to your .env file or hosting environment variables."
        )

    logger.info("Connecting to MongoDB Atlas…")

    try:
        _client = MongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=10_000,  # 10 s — fast fail on bad URI
            connectTimeoutMS=10_000,
            socketTimeoutMS=30_000,
            # Keeps a small pool for serverless/cloud environments.
            maxPoolSize=10,
            minPoolSize=1,
        )

        # Force a real round-trip to verify credentials & network access.
        _client.admin.command("ping")

        _database = _client[settings.mongodb_db_name]

        # Log the DB name but NOT the URI (which contains credentials).
        logger.info("MongoDB connected — database: %s", settings.mongodb_db_name)

    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        # Reset so partial state is not reused.
        _client = None
        _database = None
        raise RuntimeError(
            f"Cannot connect to MongoDB. "
            f"Check MONGODB_URI and network/firewall settings. Detail: {exc}"
        ) from exc
    except ConfigurationError as exc:
        _client = None
        _database = None
        raise RuntimeError(
            f"MongoDB configuration error. "
            f"Verify MONGODB_URI format. Detail: {exc}"
        ) from exc


def close() -> None:
    """
    Cleanly close the MongoDB client.

    Called during application shutdown (FastAPI lifespan).
    Safe to call even if connect() was never called.
    """
    global _client, _database

    if _client is not None:
        _client.close()
        logger.info("MongoDB connection closed.")

    _client = None
    _database = None


def get_db() -> Database:
    """
    Return the active database instance.

    Raises RuntimeError if called before connect() succeeds — this
    indicates a programming error (e.g., calling outside lifespan context).
    """
    if _database is None:
        raise RuntimeError(
            "Database is not initialised. "
            "Ensure connect() was called during application startup."
        )
    return _database


def get_collection(name: str):
    """
    Convenience shortcut: return a named collection from the active database.

    Args:
        name: Collection name, e.g. 'orders', 'users'.

    Returns:
        pymongo.collection.Collection
    """
    return get_db()[name]
