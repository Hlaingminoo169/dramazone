"""
app/services/order_service.py

Order lifecycle management.

All order creation, status transitions, and retrieval live here.
Handlers call these functions — they contain NO business logic themselves.

Atomicity:
  Approve/Reject use a conditional find_one_and_update that only succeeds
  when the order is in WAITING_APPROVAL status, preventing duplicate
  processing even if two admins act simultaneously.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.database.mongodb import get_collection
from app.types import Collection, OrderStatus
from app.utils.order_code import generate_order_code

logger = logging.getLogger(__name__)


def create_order(
    telegram_user_id: int,
    quantity: int,
    amount: int,
    payment_method: str,
    selected_movies: List[Dict[str, Any]],  # snapshots: [{movieId, title, channelLink}]
) -> dict:
    """
    Create a new order in PENDING_PAYMENT status.

    Retries up to 3 times on order code collision (extremely rare).
    Raises RuntimeError if all retries fail.

    Args:
        telegram_user_id: Customer's Telegram user ID.
        quantity: Number of movies in the package.
        amount: Total price in MMK.
        payment_method: "KPay" or "Wave".
        selected_movies: Snapshot list of {movieId, title, channelLink}.

    Returns:
        The inserted order document.
    """
    col = get_collection(Collection.ORDERS)
    now = datetime.now(timezone.utc)

    for attempt in range(3):
        order_code = generate_order_code()
        doc = {
            "orderCode": order_code,
            "telegramUserId": telegram_user_id,
            "quantity": quantity,
            "amount": amount,
            "paymentMethod": payment_method,
            "status": OrderStatus.PENDING_PAYMENT,
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
            result = col.insert_one(doc)
            doc["_id"] = result.inserted_id
            logger.info(
                "Order created: %s for user %s amount=%d",
                order_code, telegram_user_id, amount,
            )
            return doc
        except DuplicateKeyError:
            logger.warning("Order code collision on %s (attempt %d)", order_code, attempt + 1)

    raise RuntimeError("Failed to generate a unique order code after 3 attempts.")


def attach_screenshot(order_id: str, file_id: str) -> Optional[dict]:
    """
    Attach the payment screenshot file ID and move order to WAITING_APPROVAL.

    Only transitions from PENDING_PAYMENT → WAITING_APPROVAL.
    Returns updated document, or None if order not found / wrong status.
    """
    col = get_collection(Collection.ORDERS)
    now = datetime.now(timezone.utc)
    return col.find_one_and_update(
        {
            "_id": ObjectId(order_id),
            "status": OrderStatus.PENDING_PAYMENT,
        },
        {
            "$set": {
                "paymentScreenshotFileId": file_id,
                "status": OrderStatus.WAITING_APPROVAL,
                "updatedAt": now,
            }
        },
        return_document=ReturnDocument.AFTER,
    )


def approve_order(order_id: str, admin_telegram_id: int) -> Optional[dict]:
    """
    Atomically approve an order.

    Only succeeds when order.status == WAITING_APPROVAL.
    Returns updated document on success, None if already processed.
    """
    col = get_collection(Collection.ORDERS)
    now = datetime.now(timezone.utc)
    doc = col.find_one_and_update(
        {
            "_id": ObjectId(order_id),
            "status": OrderStatus.WAITING_APPROVAL,
        },
        {
            "$set": {
                "status": OrderStatus.APPROVED,
                "approvedBy": admin_telegram_id,
                "approvedAt": now,
                "updatedAt": now,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if doc:
        logger.info("Order %s approved by admin %s", doc["orderCode"], admin_telegram_id)
    return doc


def reject_order(
    order_id: str,
    admin_telegram_id: int,
    reason: str,
) -> Optional[dict]:
    """
    Atomically reject an order with a reason.

    Only succeeds when order.status == WAITING_APPROVAL.
    Returns updated document on success, None if already processed.
    """
    col = get_collection(Collection.ORDERS)
    now = datetime.now(timezone.utc)
    doc = col.find_one_and_update(
        {
            "_id": ObjectId(order_id),
            "status": OrderStatus.WAITING_APPROVAL,
        },
        {
            "$set": {
                "status": OrderStatus.REJECTED,
                "rejectionReason": reason,
                "rejectedBy": admin_telegram_id,
                "rejectedAt": now,
                "updatedAt": now,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if doc:
        logger.info("Order %s rejected by admin %s", doc["orderCode"], admin_telegram_id)
    return doc


def get_order_by_id(order_id: str) -> Optional[dict]:
    """Return an order by its MongoDB _id string."""
    try:
        oid = ObjectId(order_id)
    except Exception:
        return None
    col = get_collection(Collection.ORDERS)
    return col.find_one({"_id": oid})


def get_orders_for_user(
    telegram_user_id: int,
    limit: int = 10,
    skip: int = 0,
) -> List[dict]:
    """
    Return paginated orders for a single customer, newest first.
    Only returns orders belonging to this user (security enforced here).
    """
    col = get_collection(Collection.ORDERS)
    return list(
        col.find({"telegramUserId": telegram_user_id})
        .sort("createdAt", -1)
        .skip(skip)
        .limit(limit)
    )


def count_orders_for_user(telegram_user_id: int) -> int:
    """Return total number of orders for a user (for pagination)."""
    col = get_collection(Collection.ORDERS)
    return col.count_documents({"telegramUserId": telegram_user_id})


def get_pending_orders(limit: int = 20) -> List[dict]:
    """Return orders awaiting admin review (WAITING_APPROVAL), newest first."""
    col = get_collection(Collection.ORDERS)
    return list(
        col.find({"status": OrderStatus.WAITING_APPROVAL})
        .sort("createdAt", -1)
        .limit(limit)
    )


def get_all_orders(limit: int = 20, skip: int = 0) -> List[dict]:
    """Return all orders (admin view), newest first."""
    col = get_collection(Collection.ORDERS)
    return list(
        col.find({})
        .sort("createdAt", -1)
        .skip(skip)
        .limit(limit)
    )


def count_all_orders() -> int:
    """Return total count of all orders (used for pagination)."""
    col = get_collection(Collection.ORDERS)
    return col.count_documents({})


def get_audit_log(limit: int = 20, skip: int = 0) -> List[dict]:
    """
    Return recently processed orders (APPROVED or REJECTED) for auditing.

    Each document includes approvedBy/rejectedBy admin Telegram IDs and timestamps,
    making it suitable for accounting reconciliation.
    """
    col = get_collection(Collection.ORDERS)
    return list(
        col.find(
            {"status": {"$in": [OrderStatus.APPROVED, OrderStatus.REJECTED]}}
        )
        .sort("updatedAt", -1)
        .skip(skip)
        .limit(limit)
    )


def get_statistics() -> Dict[str, Any]:
    """Return basic order statistics for the admin dashboard."""
    col = get_collection(Collection.ORDERS)
    pipeline = [
        {
            "$group": {
                "_id": "$status",
                "count": {"$sum": 1},
                "total_amount": {"$sum": "$amount"},
            }
        }
    ]
    results = list(col.aggregate(pipeline))
    stats: Dict[str, Any] = {
        "by_status": {},
        "total_orders": 0,
        "total_approved_amount": 0,
    }
    for row in results:
        status = row["_id"]
        stats["by_status"][status] = {
            "count": row["count"],
            "total_amount": row["total_amount"],
        }
        stats["total_orders"] += row["count"]
        if status == OrderStatus.APPROVED:
            stats["total_approved_amount"] = row["total_amount"]
    return stats
