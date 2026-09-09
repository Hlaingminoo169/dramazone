"""
app/services/movie_service.py
─────────────────────────────────────────────────────────────────────────────
VIP movie catalog service.

All queries filter isActive=True so disabled movies are transparently hidden.
The watchLink field is NEVER returned in catalog queries — only in
approved-order delivery (req #27).
"""
from __future__ import annotations

import logging

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING

from app.database.collections import MOVIES

logger = logging.getLogger(__name__)

# Projection for catalog display — deliberately excludes watchLink
_CATALOG_PROJECTION = {"title": 1, "_id": 1}

# Projection for order delivery — includes watchLink (approved orders only)
_DELIVERY_PROJECTION = {"title": 1, "watchLink": 1, "_id": 1}


async def get_active_movies(db: AsyncIOMotorDatabase) -> list[dict]:
    """
    Return all active movies sorted by title.
    Only title + _id are returned — watchLink is excluded (req #27).
    """
    cursor = db[MOVIES].find(
        {"isActive": True},
        _CATALOG_PROJECTION,
    ).sort("title", ASCENDING)
    return await cursor.to_list(length=None)


async def get_movies_by_ids(
    db: AsyncIOMotorDatabase,
    movie_ids: list[str],
    include_watch_link: bool = False,
) -> list[dict]:
    """
    Fetch movie documents by their string ObjectId list.

    include_watch_link=True only when delivering approved order content (req #27).
    """
    projection = _DELIVERY_PROJECTION if include_watch_link else _CATALOG_PROJECTION
    object_ids = [ObjectId(mid) for mid in movie_ids]

    cursor = db[MOVIES].find(
        {"_id": {"$in": object_ids}, "isActive": True},
        projection,
    )
    return await cursor.to_list(length=None)


async def get_movie_count(db: AsyncIOMotorDatabase) -> int:
    """Count of active movies — used to validate catalog is seeded."""
    return await db[MOVIES].count_documents({"isActive": True})
