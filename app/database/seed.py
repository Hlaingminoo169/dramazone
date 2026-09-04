"""
app/database/seed.py
====================
Seeds initial data (movies, settings) into MongoDB on first run.
Safe to call multiple times — uses upsert so existing data is not duplicated.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from pymongo.database import Database

logger = logging.getLogger(__name__)

NOW = datetime.now(timezone.utc)

INITIAL_MOVIES = [
    {
        "title": "ဆယ်နှစ်အကြာမှာပြန်ဆုံတဲ့ကံကြမ္မာ",
        "description": "",
        "channelLink": "https://t.me/+CuZJlvkZQjllZDU1",
        "isActive": True,
        "createdAt": NOW,
        "updatedAt": NOW,
    },
    {
        "title": "ဂိုဏ်းချုပ်ကြီးရဲ့နှလုံးသားပိုင်ရှင်",
        "description": "",
        "channelLink": "https://t.me/+g3SFgjUxfu02MDc1",
        "isActive": True,
        "createdAt": NOW,
        "updatedAt": NOW,
    },
    {
        "title": "ဟန်ဆောင်ကောင်းတဲ့အမတ်မင်း",
        "description": "",
        "channelLink": "https://t.me/+Y7aQR_efx_o2MDhl",
        "isActive": True,
        "createdAt": NOW,
        "updatedAt": NOW,
    },
    {
        "title": "မျက်နှာဖုံးအောက်က ကြာပန်းအလှ",
        "description": "",
        "channelLink": "https://t.me/+wOGC1wAeKyI3M2Q1",
        "isActive": True,
        "createdAt": NOW,
        "updatedAt": NOW,
    },
    {
        "title": "ဝတုတ်ရဲ့ ကလဲ့စား",
        "description": "",
        "channelLink": "https://t.me/+07coYSluVRljY2Zl",
        "isActive": True,
        "createdAt": NOW,
        "updatedAt": NOW,
    },
    {
        "title": "လေပြေမှားတဲ့နွေဦး ရေကြည်အေးတဲ့ဆောင်းဦး",
        "description": "",
        "channelLink": "https://t.me/+ueVMFDRN1jVhNmNl",
        "isActive": True,
        "createdAt": NOW,
        "updatedAt": NOW,
    },
]

INITIAL_SETTINGS = [
    # Pricing: key = "pricing", value = list of {quantity, price, label}
    {
        "key": "pricing",
        "value": [
            {"quantity": 1, "price": 1500, "label": "1 ကား - 1,500 MMK"},
            {"quantity": 2, "price": 3000, "label": "2 ကား - 3,000 MMK"},
            {"quantity": 3, "price": 4500, "label": "3 ကား - 4,500 MMK"},
            {"quantity": 4, "price": 6000, "label": "4 ကား - 6,000 MMK"},
            {"quantity": 5, "price": 5000, "label": "5 ကား - 5,000 MMK ✨"},
        ],
        "updatedAt": NOW,
    },
]


def seed_movies(db: Database) -> None:
    """Insert movies if they do not already exist (match by title)."""
    inserted = 0
    for movie in INITIAL_MOVIES:
        result = db.movies.update_one(
            {"title": movie["title"]},
            {"$setOnInsert": movie},
            upsert=True,
        )
        if result.upserted_id:
            inserted += 1
    logger.info("Movies seeded: %d inserted, %d already existed.", inserted, len(INITIAL_MOVIES) - inserted)


def seed_settings(db: Database) -> None:
    """Insert settings if they do not already exist (match by key)."""
    inserted = 0
    for setting in INITIAL_SETTINGS:
        result = db.settings.update_one(
            {"key": setting["key"]},
            {"$setOnInsert": setting},
            upsert=True,
        )
        if result.upserted_id:
            inserted += 1
    logger.info("Settings seeded: %d inserted.", inserted)


def run_seed(db: Database) -> None:
    """Run all seed operations."""
    seed_movies(db)
    seed_settings(db)
    logger.info("Database seeding complete.")
