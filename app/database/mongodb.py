"""
app/database/mongodb.py
=======================
MongoDB connection management with connection reuse.
A single MongoClient is created once and reused across requests.
"""

from __future__ import annotations

import logging
from typing import Optional

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: Optional[MongoClient] = None


def get_client() -> MongoClient:
    """Return a cached MongoClient, creating it on first call."""
    global _client
    if _client is None:
        settings = get_settings()
        logger.info("Creating new MongoDB client connection.")
        _client = MongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            socketTimeoutMS=30000,
            maxPoolSize=10,
        )
    return _client


def get_db() -> Database:
    """Return the application database."""
    settings = get_settings()
    return get_client()[settings.mongodb_db_name]


def ping_db() -> bool:
    """Health-check: return True if MongoDB is reachable."""
    try:
        get_client().admin.command("ping")
        logger.info("MongoDB ping successful.")
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error("MongoDB ping failed: %s", e)
        return False


def close_client() -> None:
    """Close the MongoDB client (call during application shutdown)."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("MongoDB client closed.")
