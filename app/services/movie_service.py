"""
app/services/movie_service.py

Movie catalogue management.

All movie data is stored in MongoDB. Handlers NEVER hard-code movie IDs,
titles, or channel links — always fetch from the database.

Initial seed data is inserted on first startup if the collection is empty.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from bson import ObjectId

from app.database.mongodb import get_collection
from app.types import Collection

logger = logging.getLogger(__name__)

# ── Initial movie catalogue ───────────────────────────────────────────────────
# Inserted once when the movies collection is empty.
# Channel links are stored as-is; admins can update them via admin panel later.
_INITIAL_MOVIES = [
    {
        "title": "ဆယ်နှစ်အကြာမှာပြန်ဆုံတဲ့ကံကြမ္မာ",
        "description": "",
        "channelLink": "https://t.me/+CuZJlvkZQjllZDU1",
        "isActive": True,
    },
    {
        "title": "ဂိုဏ်းချုပ်ကြီးရဲ့နှလုံးသားပိုင်ရှင်",
        "description": "",
        "channelLink": "https://t.me/+g3SFgjUxfu02MDc1",
        "isActive": True,
    },
    {
        "title": "ဟန်ဆောင်ကောင်းတဲ့အမတ်မင်း",
        "description": "",
        "channelLink": "https://t.me/+Y7aQR_efx_o2MDhl",
        "isActive": True,
    },
    {
        "title": "မျက်နှာဖုံးအောက်က ကြာပန်းအလှ",
        "description": "",
        "channelLink": "https://t.me/+wOGC1wAeKyI3M2Q1",
        "isActive": True,
    },
    {
        "title": "ဝတုတ်ရဲ့ ကလဲ့စား",
        "description": "",
        "channelLink": "https://t.me/+07coYSluVRljY2Zl",
        "isActive": True,
    },
    {
        "title": "လေပြေမှားတဲ့နွေဦး ရေကြည်အေးတဲ့ဆောင်းဦး",
        "description": "",
        "channelLink": "https://t.me/+ueVMFDRN1jVhNmNl",
        "isActive": True,
    },
]


def seed_movies() -> None:
    """
    Insert initial movie data if the collection is empty.
    Safe to call on every startup.
    """
    col = get_collection(Collection.MOVIES)
    if col.count_documents({}) == 0:
        now = datetime.now(timezone.utc)
        docs = [
            {**m, "createdAt": now, "updatedAt": now}
            for m in _INITIAL_MOVIES
        ]
        result = col.insert_many(docs)
        logger.info("Seeded %d movies into the database.", len(result.inserted_ids))
    else:
        logger.debug("Movie collection already populated — skipping seed.")


def get_active_movies() -> List[dict]:
    """Return all active movies sorted by insertion order."""
    col = get_collection(Collection.MOVIES)
    return list(col.find({"isActive": True}).sort("_id", 1))


def get_movie_by_id(movie_id: str) -> Optional[dict]:
    """
    Return a single active movie by its ObjectId string.

    Returns None if not found or not active — callers must treat
    unknown / inactive IDs as invalid to prevent client-provided
    movie ID exploitation.
    """
    try:
        oid = ObjectId(movie_id)
    except Exception:
        return None
    col = get_collection(Collection.MOVIES)
    return col.find_one({"_id": oid, "isActive": True})


def get_movies_by_ids(movie_ids: List[str]) -> List[dict]:
    """
    Return multiple active movies by a list of ObjectId strings.

    Only movies that exist AND are active are returned.
    The caller should verify len(result) == len(movie_ids).
    """
    oids = []
    for mid in movie_ids:
        try:
            oids.append(ObjectId(mid))
        except Exception:
            pass

    if not oids:
        return []

    col = get_collection(Collection.MOVIES)
    return list(col.find({"_id": {"$in": oids}, "isActive": True}))
