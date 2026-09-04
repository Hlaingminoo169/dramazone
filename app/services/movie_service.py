"""
app/services/movie_service.py
==============================
All movie-related database operations.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from bson import ObjectId
from pymongo.database import Database

logger = logging.getLogger(__name__)


def get_active_movies(db: Database) -> list[dict]:
    """Return all active movies ordered by creation date."""
    return list(
        db.movies.find({"isActive": True}).sort("createdAt", 1)
    )


def get_movie_by_id(db: Database, movie_id: str) -> dict | None:
    """Return a single movie by its ObjectId string, or None."""
    try:
        oid = ObjectId(movie_id)
    except Exception:
        return None
    return db.movies.find_one({"_id": oid})


def get_movies_by_ids(db: Database, movie_ids: list[str]) -> list[dict]:
    """Return multiple movies by their ObjectId strings."""
    oids = []
    for mid in movie_ids:
        try:
            oids.append(ObjectId(mid))
        except Exception:
            logger.warning("Invalid movie ObjectId: %s", mid)
    if not oids:
        return []
    return list(db.movies.find({"_id": {"$in": oids}}))


def snapshot_movie(movie: dict) -> dict:
    """
    Create a snapshot of a movie for embedding in an order document.
    Preserves title and channel link at time of purchase for historical accuracy.
    """
    return {
        "movieId": str(movie["_id"]),
        "title": movie.get("title", ""),
        "channelLink": movie.get("channelLink", ""),
    }
