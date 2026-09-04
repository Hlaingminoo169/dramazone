"""
app/services/order_service.py
==============================
All order-related database operations.
Uses atomic MongoDB operations to prevent race conditions.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.types import OrderStatus, PaymentMethod
from app.utils.order_code import generate_order_code

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_order(
    db: Database,
    telegram_user_id: int,
    quantity: int,
    amount: int,
    selected_movies: list[dict],  # list of movie snapshots
) -> dict:
    """
    Create a new order in PENDING_PAYMENT status.
    Retries on duplicate orderCode (collision is rare but possible).
    Returns the inserted order document.
    """
    for attempt in range(5):
        order_code = generate_order_code()
        now = _now()
        doc = {
            "orderCode": order_code,
            "telegramUserId": telegram_user_id,
            "quantity": quantity,
            "amount": amount,
            "paymentMethod": None,
            "status": OrderStatus.PENDING_PAYMENT.value,
            "selectedMovies": selected_movies,
            "paymentScreenshotFileId": None,
            "rejectionReason": None,
            "approvedBy": None,
            "approvedAt": None,
            "rejectedBy": None,
            "rejectedAt": None,
            "createdAt": now,
            "updatedAt": now,
        }
        try:
            result = db.orders.insert_one(doc)
            doc["_id"] = result.inserted_id
            logger.info("Order created: %s for user %d", order_code, telegram_user_id)
            return doc
        except DuplicateKeyError:
            logger.warning("Order code collision on attempt %d: %s", attempt + 1, order_code)

    raise RuntimeError("Failed to generate unique order code after 5 attempts.")


def get_order_by_code(db: Database, order_code: str) -> dict | None:
    """Return order by its human-readable code."""
    return db.orders.find_one({"orderCode": order_code})


def get_pending_payment_order(db: Database, telegram_user_id: int) -> dict | None:
    """Return the most recent PENDING_PAYMENT order for a user."""
    return db.orders.find_one(
        {
            "telegramUserId": telegram_user_id,
            "status": OrderStatus.PENDING_PAYMENT.value,
        },
        sort=[("createdAt", -1)],
    )


def get_waiting_approval_order(db: Database, telegram_user_id: int) -> dict | None:
    """Return the most recent WAITING_APPROVAL order for a user."""
    return db.orders.find_one(
        {
            "telegramUserId": telegram_user_id,
            "status": OrderStatus.WAITING_APPROVAL.value,
        },
        sort=[("createdAt", -1)],
    )


def submit_payment_screenshot(
    db: Database,
    order_code: str,
    telegram_user_id: int,
    file_id: str,
    payment_method: PaymentMethod,
) -> bool:
    """
    Record payment screenshot and move order to WAITING_APPROVAL.
    Returns True on success, False if order not found or already processed.
    Validates ownership — user can only update their own order.
    """
    now = _now()
    result = db.orders.update_one(
        {
            "orderCode": order_code,
            "telegramUserId": telegram_user_id,
            "status": OrderStatus.PENDING_PAYMENT.value,
        },
        {
            "$set": {
                "paymentScreenshotFileId": file_id,
                "paymentMethod": payment_method.value,
                "status": OrderStatus.WAITING_APPROVAL.value,
                "updatedAt": now,
            }
        },
    )
    if result.modified_count == 1:
        logger.info("Order %s moved to WAITING_APPROVAL.", order_code)
        return True
    logger.warning(
        "Failed to submit screenshot for order %s (user %d) — not found or wrong status.",
        order_code,
        telegram_user_id,
    )
    return False


def approve_order(
    db: Database,
    order_code: str,
    approved_by: int,  # admin Telegram ID
) -> tuple[bool, str]:
    """
    Atomically approve an order.
    Returns (success: bool, message: str).
    Uses findOneAndUpdate to prevent race conditions between two admins.
    """
    now = _now()
    updated = db.orders.find_one_and_update(
        {
            "orderCode": order_code,
            "status": OrderStatus.WAITING_APPROVAL.value,
        },
        {
            "$set": {
                "status": OrderStatus.APPROVED.value,
                "approvedBy": approved_by,
                "approvedAt": now,
                "updatedAt": now,
            }
        },
        return_document=True,  # return the updated document
    )
    if updated:
        logger.info("Order %s approved by admin %d.", order_code, approved_by)
        return True, "approved"

    # Check if already processed
    existing = get_order_by_code(db, order_code)
    if existing and existing["status"] != OrderStatus.WAITING_APPROVAL.value:
        return False, "already_processed"

    return False, "not_found"


def reject_order(
    db: Database,
    order_code: str,
    rejected_by: int,
    reason: str,
) -> tuple[bool, str]:
    """
    Atomically reject an order with a reason.
    Returns (success: bool, message: str).
    """
    now = _now()
    updated = db.orders.find_one_and_update(
        {
            "orderCode": order_code,
            "status": OrderStatus.WAITING_APPROVAL.value,
        },
        {
            "$set": {
                "status": OrderStatus.REJECTED.value,
                "rejectionReason": reason,
                "rejectedBy": rejected_by,
                "rejectedAt": now,
                "updatedAt": now,
            }
        },
        return_document=True,
    )
    if updated:
        logger.info("Order %s rejected by admin %d.", order_code, rejected_by)
        return True, "rejected"

    existing = get_order_by_code(db, order_code)
    if existing and existing["status"] != OrderStatus.WAITING_APPROVAL.value:
        return False, "already_processed"

    return False, "not_found"


def cancel_order(db: Database, order_code: str, telegram_user_id: int) -> bool:
    """Cancel a PENDING_PAYMENT order. User can only cancel their own orders."""
    now = _now()
    result = db.orders.update_one(
        {
            "orderCode": order_code,
            "telegramUserId": telegram_user_id,
            "status": OrderStatus.PENDING_PAYMENT.value,
        },
        {
            "$set": {
                "status": OrderStatus.CANCELLED.value,
                "updatedAt": now,
            }
        },
    )
    return result.modified_count == 1


def get_user_orders(
    db: Database,
    telegram_user_id: int,
    limit: int = 10,
    skip: int = 0,
) -> list[dict]:
    """Return a user's order history, newest first. Only their own orders."""
    return list(
        db.orders.find(
            {"telegramUserId": telegram_user_id}
        )
        .sort("createdAt", -1)
        .skip(skip)
        .limit(limit)
    )


def get_pending_orders(db: Database, limit: int = 20) -> list[dict]:
    """Return all WAITING_APPROVAL orders for admin review, oldest first."""
    return list(
        db.orders.find({"status": OrderStatus.WAITING_APPROVAL.value})
        .sort("createdAt", 1)
        .limit(limit)
    )


def get_all_orders(db: Database, limit: int = 20, skip: int = 0) -> list[dict]:
    """Return all orders for admin, newest first."""
    return list(
        db.orders.find({})
        .sort("createdAt", -1)
        .skip(skip)
        .limit(limit)
    )


def get_statistics(db: Database) -> dict:
    """Return basic order statistics for the admin dashboard."""
    pipeline = [
        {
            "$group": {
                "_id": "$status",
                "count": {"$sum": 1},
                "total_amount": {"$sum": "$amount"},
            }
        }
    ]
    results = list(db.orders.aggregate(pipeline))
    stats: dict = {
        "total_orders": db.orders.count_documents({}),
        "total_users": db.users.count_documents({}),
        "by_status": {},
        "total_revenue": 0,
    }
    for row in results:
        status = row["_id"]
        stats["by_status"][status] = row["count"]
        if status == OrderStatus.APPROVED.value:
            stats["total_revenue"] = row["total_amount"]
    return stats
