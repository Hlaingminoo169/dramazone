"""
app/handlers/admin/orders.py

Admin order viewing — pending orders, all orders, statistics — Step 12.
"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from app.config import settings
from app.services.order_service import get_pending_orders, get_all_orders, get_statistics
from app.types import OrderStatus
from app.utils.pricing import format_price

logger = logging.getLogger(__name__)


def _require_admin(tg_id: int) -> bool:
    return settings.is_admin(tg_id)


def _format_order_summary(order: dict, index: int) -> str:
    movies = order.get("selectedMovies", [])
    movie_list = "\n".join(f"    • {m['title']}" for m in movies)
    created = order.get("createdAt")
    date_str = created.strftime("%Y-%m-%d %H:%M") if created else "—"
    return (
        f"*{index}. Order `{order['orderCode']}`*\n"
        f"User ID: `{order['telegramUserId']}`\n"
        f"ရက်: {date_str}\n"
        f"ကားများ:\n{movie_list}\n"
        f"ငွေ: {format_price(order['amount'])}\n"
        f"Status: {order['status']}\n"
    )


async def show_pending_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if not _require_admin(tg_user.id):
        await update.message.reply_text("🚫 Admin only.")
        return

    orders = get_pending_orders(limit=20)
    if not orders:
        await update.message.reply_text("✅ Pending orders မရှိပါ။")
        return

    text = f"🔔 *Pending Orders ({len(orders)} ခု)*\n\n"
    text += "\n".join(
        _format_order_summary(o, i + 1) for i, o in enumerate(orders)
    )
    await update.message.reply_text(text[:4000], parse_mode="Markdown")


async def show_all_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if not _require_admin(tg_user.id):
        await update.message.reply_text("🚫 Admin only.")
        return

    orders = get_all_orders(limit=20)
    if not orders:
        await update.message.reply_text("📦 Order မရှိသေးပါ။")
        return

    text = f"📦 *All Orders (ပြီးဆုံးသည့် 20 ခု)*\n\n"
    text += "\n".join(
        _format_order_summary(o, i + 1) for i, o in enumerate(orders)
    )
    await update.message.reply_text(text[:4000], parse_mode="Markdown")


async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    if not _require_admin(tg_user.id):
        await update.message.reply_text("🚫 Admin only.")
        return

    stats = get_statistics()
    by_status = stats.get("by_status", {})

    def _stat(status: str) -> str:
        s = by_status.get(status, {})
        return f"{s.get('count', 0)} ခု ({format_price(s.get('total_amount', 0))})"

    text = (
        f"📊 *Statistics*\n\n"
        f"စုစုပေါင်း Orders: {stats['total_orders']} ခု\n\n"
        f"⏳ Pending Payment: {_stat(OrderStatus.PENDING_PAYMENT)}\n"
        f"🔍 Waiting Approval: {_stat(OrderStatus.WAITING_APPROVAL)}\n"
        f"✅ Approved: {_stat(OrderStatus.APPROVED)}\n"
        f"❌ Rejected: {_stat(OrderStatus.REJECTED)}\n"
        f"🚫 Cancelled: {_stat(OrderStatus.CANCELLED)}\n\n"
        f"💰 အတည်ပြုပြီး ငွေပမာဏ: {format_price(stats['total_approved_amount'])}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


def register(app: Application) -> None:
    app.add_handler(MessageHandler(filters.Text(["🔔 Pending Orders"]), show_pending_orders))
    app.add_handler(MessageHandler(filters.Text(["📦 All Orders"]), show_all_orders))
    app.add_handler(MessageHandler(filters.Text(["📊 Statistics"]), show_statistics))
