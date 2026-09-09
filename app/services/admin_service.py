"""
app/services/admin_service.py
────────────────────────────────────────────────────────────────────────
Admin Analytics & Order Action Management Service.

Handles:
- Admin authorization validation
- Admin Analytics Dashboard metrics calculation (req #37)
- Order Approval & Watch Link delivery trigger
- Order Rejection & Customer notification trigger
"""

import logging
from datetime import datetime, time
from typing import Dict, Any, Optional, Tuple, List
import pytz

from app.config import get_settings
from app.database.connection import get_db
from app.models.order import Order, OrderStatus
from app.services.order_service import order_service
from app.services.movie_service import movie_service
from app.services.notifier import notifier_service

config = get_settings()
logger = logging.getLogger("dramazone.services.admin")


class AdminService:
    """Admin operations service."""

    def is_admin(self, telegram_id: int) -> bool:
        """Check if telegram_id is authorized as an Admin."""
        return telegram_id in config.admin_ids

    async def get_dashboard_stats(self) -> Dict[str, Any]:
        """Calculate dashboard statistics for admin summary report."""
        db = get_db()
        users_col = db["users"]
        orders_col = db["orders"]

        total_users = await users_col.count_documents({})
        total_orders = await orders_col.count_documents({})

        pending_count = await orders_col.count_documents({
            "$or": [
                {"status": OrderStatus.WAITING_APPROVAL.value},
                {"status": "PAYMENT_SUBMITTED"}
            ]
        })
        approved_count = await orders_col.count_documents({"status": OrderStatus.APPROVED.value})
        rejected_count = await orders_col.count_documents({"status": OrderStatus.REJECTED.value})

        # Calculate Total Revenue (APPROVED orders)
        pipeline_total_rev = [
            {"$match": {"status": OrderStatus.APPROVED.value}},
            {"$group": {"_id": None, "totalRevenue": {"$sum": "$totalPrice"}}}
        ]
        rev_res = await orders_col.aggregate(pipeline_total_rev).to_list(length=1)
        total_revenue = rev_res[0]["totalRevenue"] if rev_res else 0

        # Calculate Today's Revenue in Asia/Yangon timezone
        try:
            tz = pytz.timezone(config.report_timezone)
            now_local = datetime.now(tz)
            start_of_day_local = datetime.combine(now_local.date(), time.min)
            # convert local start of day to UTC for MongoDB query
            start_of_day_utc = tz.localize(start_of_day_local).astimezone(pytz.utc).replace(tzinfo=None)
        except Exception:
            start_of_day_utc = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        pipeline_today_rev = [
            {
                "$match": {
                    "status": OrderStatus.APPROVED.value,
                    "createdAt": {"$gte": start_of_day_utc}
                }
            },
            {"$group": {"_id": None, "todayRevenue": {"$sum": "$totalPrice"}, "todayCount": {"$sum": 1}}}
        ]
        today_res = await orders_col.aggregate(pipeline_today_rev).to_list(length=1)
        today_revenue = today_res[0]["todayRevenue"] if today_res else 0
        today_approved_count = today_res[0]["todayCount"] if today_res else 0

        return {
            "total_users": total_users,
            "total_orders": total_orders,
            "pending_count": pending_count,
            "approved_count": approved_count,
            "rejected_count": rejected_count,
            "total_revenue": total_revenue,
            "today_revenue": today_revenue,
            "today_approved_count": today_approved_count,
        }

    async def get_pending_orders(self, limit: int = 20) -> List[Order]:
        """Fetch all orders currently in WAITING_APPROVAL status."""
        db = get_db()
        orders_col = db["orders"]
        cursor = orders_col.find({
            "$or": [
                {"status": OrderStatus.WAITING_APPROVAL.value},
                {"status": "PAYMENT_SUBMITTED"}
            ]
        }).sort("createdAt", 1).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [Order(**d) for d in docs]

    async def approve_order(
        self,
        order_code: str,
        admin_id: int,
        admin_username: str = ""
    ) -> Tuple[bool, str, Optional[Order]]:
        """
        Approve an order atomically.

        Enforces:
        - Order must be in WAITING_APPROVAL state.
        - Increments user's total orders count.
        - Triggers customer watch links notification.
        """
        db = get_db()
        orders_col = db["orders"]
        users_col = db["users"]

        now = datetime.utcnow()
        update_doc = {
            "$set": {
                "status": OrderStatus.APPROVED.value,
                "approvedByAdminId": admin_id,
                "approvedAt": now,
                "updatedAt": now
            }
        }

        # Atomic find-and-update (Filter on status to prevent race conditions)
        raw_order = await orders_col.find_one_and_update(
            {
                "orderCode": order_code,
                "status": {"$in": [OrderStatus.WAITING_APPROVAL.value, "PAYMENT_SUBMITTED"]}
            },
            update_doc,
            return_document=True
        )

        if not raw_order:
            # Check if order exists in another state
            existing = await orders_col.find_one({"orderCode": order_code})
            if not existing:
                return False, "Order ရှာမတွေ့ပါ။", None
            return False, f"Order သည် အဆင့် {existing.get('status')} တွင် ရောက်ရှိနေပြီး ဖြစ်ပါသည်။", Order(**existing)

        order = Order(**raw_order)

        # Increment user total orders count
        await users_col.update_one(
            {"telegramId": order.telegramUserId},
            {"$inc": {"totalOrders": 1}}
        )

        # Get watch links for movies
        movies = await movie_service.get_movies_by_ids(order.movieIds, include_watch_link=True)

        # Notify Customer
        await notifier_service.notify_customer_order_approved(order, movies)

        logger.info(f"Order #{order_code} approved by admin {admin_id} (@{admin_username}).")
        return True, "Order အား အောင်မြင်စွာ Approve ပြုလုပ်ပြီးပါပြီ။", order

    async def reject_order(
        self,
        order_code: str,
        admin_id: int,
        admin_username: str = "",
        reason: str = "ငွေလွှဲပြေစာ အချက်အလက် မကိုက်ညီပါ"
    ) -> Tuple[bool, str, Optional[Order]]:
        """
        Reject an order atomically.

        Enforces:
        - Order must be in PAYMENT_SUBMITTED state.
        - Triggers customer rejection notification.
        """
        db = get_db()
        orders_col = db["orders"]

        now = datetime.utcnow()
        update_doc = {
            "$set": {
                "status": OrderStatus.REJECTED.value,
                "approvedByAdminId": admin_id,
                "rejectReason": reason,
                "updatedAt": now
            }
        }

        raw_order = await orders_col.find_one_and_update(
            {
                "orderCode": order_code,
                "status": {"$in": [OrderStatus.WAITING_APPROVAL.value, "PAYMENT_SUBMITTED"]}
            },
            update_doc,
            return_document=True
        )

        if not raw_order:
            existing = await orders_col.find_one({"orderCode": order_code})
            if not existing:
                return False, "Order ရှာမတွေ့ပါ။", None
            return False, f"Order သည် အဆင့် {existing.get('status')} တွင် ရောက်ရှိနေပြီး ဖြစ်ပါသည်။", Order(**existing)

        order = Order(**raw_order)

        # Notify Customer of Rejection
        await notifier_service.notify_customer_order_rejected(order, reason)

        logger.info(f"Order #{order_code} rejected by admin {admin_id} (@{admin_username}) - Reason: {reason}.")
        return True, f"Order အား Reject ပြုလုပ်ပြီးပါပြီ။ (Reason: {reason})", order


admin_service = AdminService()
