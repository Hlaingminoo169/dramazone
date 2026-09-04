"""
app/handlers/admin/orders.py
==============================
Admin order listing and statistics views.
"""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.database.mongodb import get_db
from app.handlers.admin.auth import is_admin, unauthorized_response
from app.services.order_service import get_all_orders, get_pending_orders, get_statistics
from app.types import OrderStatus

logger = logging.getLogger(__name__)

STATUS_EMOJI = {
    OrderStatus.PENDING_PAYMENT.value: "⏳",
    OrderStatus.WAITING_APPROVAL.value: "🔍",
    OrderStatus.APPROVED.value: "✅",
    OrderStatus.REJECTED.value: "❌",
    OrderStatus.CANCELLED.value: "🚫",
}


def _format_order_summary(order: dict) -> str:
    code = order.get("orderCode", "N/A")
    status = order.get("status", "")
    emoji = STATUS_EMOJI.get(status, "❓")
    amount = order.get("amount", 0)
    quantity = order.get("quantity", 0)
    tid = order.get("telegramUserId", "N/A")
    created_at = order.get("createdAt")
    date_str = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "N/A"
    movies = ", ".join(m.get("title", "?")[:15] for m in order.get("selectedMovies", []))
    return (
        f"{emoji} <b>{code}</b>\n"
        f"👤 User: <code>{tid}</code>\n"
        f"🎬 {movies}\n"
        f"💰 {amount:,} MMK | {quantity} ကား\n"
        f"📅 {date_str}"
    )


async def show_pending_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all WAITING_APPROVAL orders."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        await unauthorized_response(update, context)
        return

    db = get_db()
    orders = get_pending_orders(db, limit=20)

    if not orders:
        text = "🔔 <b>Pending Orders</b>\n\nစောင့်ဆိုင်းနေသော order မရှိပါ။"
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 Admin Menu", callback_data="admin:home")
        ]])
        query = update.callback_query
        if query:
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
        return

    lines = [f"🔔 <b>Pending Orders ({len(orders)})</b>\n"]
    buttons = []

    for order in orders:
        lines.append(_format_order_summary(order))
        lines.append("")
        code = order.get("orderCode")
        buttons.append([
            InlineKeyboardButton(f"✅ Approve {code}", callback_data=f"approve:{code}"),
            InlineKeyboardButton(f"❌ Reject {code}", callback_data=f"reject:{code}"),
        ])

    buttons.append([InlineKeyboardButton("🏠 Admin Menu", callback_data="admin:home")])

    text = "\n".join(lines)
    query = update.callback_query
    if query:
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))


async def show_all_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all recent orders."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        await unauthorized_response(update, context)
        return

    db = get_db()
    orders = get_all_orders(db, limit=15)

    if not orders:
        text = "📦 <b>All Orders</b>\n\nOrder မရှိသေးပါ။"
    else:
        lines = [f"📦 <b>All Orders ({len(orders)} most recent)</b>\n"]
        for order in orders:
            lines.append(_format_order_summary(order))
            lines.append("")
        text = "\n".join(lines)

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🏠 Admin Menu", callback_data="admin:home")
    ]])

    query = update.callback_query
    if query:
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show aggregate statistics."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        await unauthorized_response(update, context)
        return

    db = get_db()
    stats = get_statistics(db)

    by_status = stats.get("by_status", {})
    text = (
        f"📊 <b>Statistics</b>\n\n"
        f"👥 Total Users: <b>{stats['total_users']:,}</b>\n"
        f"📦 Total Orders: <b>{stats['total_orders']:,}</b>\n"
        f"💰 Total Revenue (Approved): <b>{stats['total_revenue']:,} MMK</b>\n\n"
        f"<b>Orders by Status:</b>\n"
        f"  ⏳ Pending Payment: {by_status.get(OrderStatus.PENDING_PAYMENT.value, 0)}\n"
        f"  🔍 Waiting Approval: {by_status.get(OrderStatus.WAITING_APPROVAL.value, 0)}\n"
        f"  ✅ Approved: {by_status.get(OrderStatus.APPROVED.value, 0)}\n"
        f"  ❌ Rejected: {by_status.get(OrderStatus.REJECTED.value, 0)}\n"
        f"  🚫 Cancelled: {by_status.get(OrderStatus.CANCELLED.value, 0)}\n"
    )

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🏠 Admin Menu", callback_data="admin:home")
    ]])

    query = update.callback_query
    if query:
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
