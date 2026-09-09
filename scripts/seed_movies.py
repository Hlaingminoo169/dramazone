"""
scripts/seed_movies.py
────────────────────────────────────────────────────────────────────────
Seed real initial movie catalog into MongoDB for DramaZone VIP Bot.

Usage:
  python -m scripts.seed_movies
"""

import asyncio
import logging
from datetime import datetime

from app.database.connection import connect_db, disconnect_db, get_db
from app.utils.logger import setup_logging

setup_logging(level="INFO")
logger = logging.getLogger("dramazone.seed")

REAL_MOVIES = [
    {
        "titleMM": "ဆယ်နှစ်အကြာမှာပြန်ဆုံတဲ့ကံကြမ္မာ",
        "titleEn": "Fate Reunited After Ten Years",
        "description": "DramaZone VIP Series",
        "watchLink": "https://t.me/+CuZJlvkZQjllZDU1",
        "isActive": True,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    },
    {
        "titleMM": "ဂိုဏ်းချုပ်ကြီးရဲ့နှလုံးသားပိုင်ရှင်",
        "titleEn": "Owner of the Chief's Heart",
        "description": "DramaZone VIP Series",
        "watchLink": "https://t.me/+g3SFgjUxfu02MDc1",
        "isActive": True,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    },
    {
        "titleMM": "ဟန်ဆောင်ကောင်းတဲ့အမတ်မင်း",
        "titleEn": "The Deceptive Minister",
        "description": "DramaZone VIP Series",
        "watchLink": "https://t.me/+Y7aQR_efx_o2MDhl",
        "isActive": True,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    },
    {
        "titleMM": "မျက်နှာဖုံးအောက်က ကြာပန်းအလှ",
        "titleEn": "Lotus Beauty Behind the Mask",
        "description": "DramaZone VIP Series",
        "watchLink": "https://t.me/+wOGC1wAeKyI3M2Q1",
        "isActive": True,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    },
    {
        "titleMM": "ဝတုတ်ရဲ့ ကလဲ့စား",
        "titleEn": "Fatty's Revenge",
        "description": "DramaZone VIP Series",
        "watchLink": "https://t.me/+07coYSluVRljY2Zl",
        "isActive": True,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    },
    {
        "titleMM": "လေပြေမှားတဲ့နွေဦး ရေကြည်အေးတဲ့ဆောင်းဦး",
        "titleEn": "Misguided Spring Breeze, Cool Winter Water",
        "description": "DramaZone VIP Series",
        "watchLink": "https://t.me/+ueVMFDRN1jVhNmNl",
        "isActive": True,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
]


async def seed() -> None:
    logger.info("Connecting to MongoDB Atlas...")
    await connect_db()
    db = get_db()

    movies_col = db["movies"]

    # Clear old dummy data
    await movies_col.delete_many({})
    logger.info("Cleared previous movie entries from collection.")

    # Insert official 6 movies
    await movies_col.insert_many(REAL_MOVIES)
    logger.info(f"Successfully seeded {len(REAL_MOVIES)} official movies into MongoDB!")

    await disconnect_db()


if __name__ == "__main__":
    asyncio.run(seed())
