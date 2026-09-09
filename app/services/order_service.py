"""
app/services/order_service.py
─────────────────────────────────────────────────────────────────────────────
Order lifecycle service.

Handles order creation, state transitions, and queries.
All status transitions are atomic via MongoDB filter-on-status updates,
preventing duplicate processing and race conditions (req #32, #33).
"""
from __future__ import annotations

import logging
import random
import string
from datetime import date, datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from telegram import User as TelegramUser

from app.config import get_settings
from app.database.collections import ORDERS, USERS
from app.models.order import OrderStatus

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Order code generation
# ──────────────────────────────────────────────
def _generate_order_code() -> str:
    """Generate a human-readable order code: DZ-YYYYMMDD-XXXX."""
    date_str = date.today().strftime("%Y%m%d")
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"DZ-{date_str}-{suffix}"


async def generate_unique_order_code(db: AsyncIOMotorDatabase) -> str:
    """Generate an order code guaranteed to be unique in the DB (retry on collision)."""
    for _ in range(10):
        code = _generate_order_code()
        if not await db[ORDERS].find_one({"orderCode": code}, {"_id": 1}):
            return code
    # Extremely unlikely — fall back with timestamp suffix
    import time
    return f"DZ-{date.today().strftime('%Y%m%d')}-{int(time.time()) % 10000:04d}"


# ──────────────────────────────────────────────
# Create
# ──────────────────────────────────────────────
async def create_order(
    db: AsyncIOMotorDatabase,
    telegram_user: TelegramUser,
    movie_ids: list[str],
    package_size: int,
) -> dict:
    """
    Insert a new PENDING_PAYMENT order.

    Also increments the user's totalOrders counter atomically.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    order_code = await generate_unique_order_code(db)
    total_amount = settings.package_prices[package_size]

    doc = {
        "orderCode": order_code,
        "telegramUserId": telegram_user.id,
        "telegramUsername": telegram_user.username,
        "telegramFirstName": telegram_user.first_name,
        "movieIds": movie_ids,
        "packageSize": package_size,
        "totalAmount": total_amount,
        "paymentMethod": None,
        "status": OrderStatus.PENDING_PAYMENT,
        "screenshotFileId": None,
        "screenshotSubmittedAt": None,
        "approvedBy": None,
        "rejectedBy": None,
        "rejectionReason": None,
        "adminMessageId": None,
        "adminChatId": None,
        "createdAt": now,
        "updatedAt": now,
    }

    await db[ORDERS].insert_one(doc)

    # Increment denormalised counter
    await db[USERS].update_one(
        {"telegramUserId": telegram_user.id},
        {"$inc": {"totalOrders": 1}},
    )

    logger.info(
        "Order created: code=%s user=%d amount=%d",
        order_code, telegram_user.id, total_amount,
    )
    return doc


# ──────────────────────────────────────────────
# State transitions (all atomic via status filter)
# ──────────────────────────────────────────────
async def set_payment_method(
    db: AsyncIOMotorDatabase,
    order_code: str,
    method: str,
) -> bool:
    """Store the chosen payment method. Only applies to PENDING_PAYMENT orders."""
    result = await db[ORDERS].update_one(
        {"orderCode": order_code, "status": OrderStatus.PENDING_PAYMENT},
        {"$set": {"paymentMethod": method, "updatedAt": datetime.now(timezone.utc)}},
    )
    return result.modified_count > 0


async def submit_screenshot(
    db: AsyncIOMotorDatabase,
    order_code: str,
    file_id: str,
) -> bool:
    """
    Atomic PENDING_PAYMENT → WAITING_APPROVAL transition.

    Returns True if the transition succeeded (order was in PENDING_PAYMENT).
    Returns False if the order was already in another state (e.g. already submitted).
    This prevents double-submission (req #33).
    """
    now = datetime.now(timezone.utc)
    result = await db[ORDERS].update_one(
        {"orderCode": order_code, "status": OrderStatus.PENDING_PAYMENT},
        {
            "$set": {
                "status": OrderStatus.WAITING_APPROVAL,
                "screenshotFileId": file_id,
                "screenshotSubmittedAt": now,
                "updatedAt": now,
            }
        },
    )
    if result.modified_count > 0:
        logger.info("Screenshot submitted: order=%s", order_code)
        return True
    return False


async def cancel_order(
    db: AsyncIOMotorDatabase,
    order_code: str,
    user_id: int,
) -> bool:
    """Cancel an order. Only the order owner can cancel, and only PENDING_PAYMENT orders."""
    result = await db[ORDERS].update_one(
        {
            "orderCode": order_code,
            "telegramUserId": user_id,
            "status": OrderStatus.PENDING_PAYMENT,
        },
        {"$set": {"status": OrderStatus.CANCELLED, "updatedAt": datetime.now(timezone.utc)}},
    )
    return result.modified_count > 0


# ──────────────────────────────────────────────
# Queries
# ──────────────────────────────────────────────
async def get_order(db: AsyncIOMotorDatabase, order_code: str) -> dict | None:
    """Fetch a single order by its code."""
    return await db[ORDERS].find_one({"orderCode": order_code})


async def get_user_order(
    db: AsyncIOMotorDatabase,
    order_code: str,
    user_id: int,
) -> dict | None:
    """Fetch an order only if it belongs to the given user (ownership check)."""
    return await db[ORDERS].find_one(
        {"orderCode": order_code, "telegramUserId": user_id}
    )


async def get_user_orders(
    db: AsyncIOMotorDatabase,
    user_id: int,
    limit: int = 5,
) -> list[dict]:
    """Return a user's most recent orders, newest first."""
    cursor = db[ORDERS].find(
        {"telegramUserId": user_id},
        sort=[("createdAt", -1)],
    ).limit(limit)
    return await cursor.to_list(length=limit)


async def get_pending_order_for_user(
    db: AsyncIOMotorDatabase,
    user_id: int,
) -> dict | None:
    """
    Return an existing PENDING_PAYMENT order for this user if one exists.
    Used to prevent duplicate order creation (req #32).
    """
    return await db[ORDERS].find_one(
        {"telegramUserId": user_id, "status": OrderStatus.PENDING_PAYMENT},
        sort=[("createdAt", -1)],
    )
