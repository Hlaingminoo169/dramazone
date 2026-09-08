"""
app/handlers/admin/orders.py

Admin order viewing — pending orders, all orders, statistics, audit log — Step 12.
"""
from __future__ import annotations

import logging
from datetime import timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from app.config import settings
from app.services.order_service import (
    get_pending_orders,
    get_all_orders,
    get_statistics,
    count_all_orders,
    get_audit_log,
)
from app.types import OrderStatus
from app.utils.pricing import format_price

logger = logging.getLogger(__name__)

ORDERS_PER_PAGE = 10


def _require_admin(tg_id: int) -> bool:
    return settings.is_admin(tg_id)


def _fmt_dt(dt) -> str:
    """Format a datetime to Myanmar-friendly string."""
    if not dt:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # Display in UTC+6:30 (Myanmar Time)
    from datetime import timedelta
    mmt = dt + timedelta(hours=6, minutes=30)
    return mmt.strftime("%Y-%m-%d %H:%M")


def _status_icon(status: str) -> str:
    icons = {
        OrderStatus.PENDING_PAYMENT: "⏳",
        OrderStatus.WAITING_APPROVAL: "🔍",
        OrderStatus.APPROVED: "✅",
        OrderStatus.REJECTED: "❌",
        OrderStatus.CANCELLED: "🚫",
    }
    return icons.get(status, "❓")


def _format_order_summary(order: dict, index: int, detailed: bool = False) -> str:
    """Format a single order for display. detailed=True adds audit fields."""
    movies = order.get("selectedMovies", [])
    movie_list = "\n".join(f"    • {m['title']}" for m in movies)
    created = order.get("createdAt")
    status = order.get("status", "—")
    icon = _status_icon(status)

    lines = [
        f"*{index}. `{order['orderCode']}`* {icon}",
        f"User ID: `{order['telegramUserId']}`",
        f"ရက်: {_fmt_dt(created)}",
        f"ကားများ:\n{movie_list}",
        f"ငွေ: {format_price(order['amount'])} ({order.get('paymentMethod', '—')})",
        f"Status: `{status}`",
    ]

    if detailed:
        # Auditing fields
        if order.get("approvedBy"):
            lines.append(f"✅ Approved by: `{order['approvedBy']}` at {_fmt_dt(order.get('approvedAt'))}")
        if order.get("rejectedBy"):
            lines.append(f"❌ Rejected by: `{order['rejectedBy']}` at {_fmt_dt(order.get('rejectedAt'))}")
        if order.get("rejectionReason"):
            lines.append(f"📝 Reason: {order['rejectionReason']}")

    return "\n".join(lines)


def _paginate_keyboard(page: int, total: int, per_page: int, prefix: str) -> InlineKeyboardMarkup | None:
    """Build a prev/next pagination keyboard."""
    total_pages = (total + per_page - 1) // per_page
    if total_pages <= 1:
        return None
    buttons = []
    row = []
    if page > 0:
        row.append(InlineKeyboardButton("◀️ Prev", callback_data=f"{prefix}:{page - 1}"))
    row.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
    if (page + 1) * per_page < total:
        row.append(InlineKeyboardButton("Next ▶️", callback_data=f"{prefix}:{page + 1}"))
    buttons.append(row)
    return InlineKeyboardMarkup(buttons)


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
    text += "\n─────────────────────\n".join(
        _format_order_summary(o, i + 1, detailed=True) for i, o in enumerate(orders)
    )
    # Telegram 4096 limit — send in chunks if needed
    await _send_long_message(update.message.reply_text, text)


async def show_all_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all orders with pagination (page 0)."""
    tg_user = update.effective_user
    if not _require_admin(tg_user.id):
        await update.message.reply_text("🚫 Admin only.")
        return
    await _send_all_orders_page(update.message.reply_text, page=0)


async def paginate_all_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle pagination callbacks for All Orders."""
    query = update.callback_query
    await query.answer()
    if not _require_admin(update.effective_user.id):
        return
    page = int(query.data.split(":")[1])
    await _send_all_orders_page(query.edit_message_text, page=page)


async def _send_all_orders_page(send_fn, page: int) -> None:
    """Fetch and send a single page of all orders."""
    skip = page * ORDERS_PER_PAGE
    orders = get_all_orders(limit=ORDERS_PER_PAGE, skip=skip)
    total = count_all_orders()

    if not orders:
        await send_fn("📦 Order မရှိသေးပါ။")
        return

    text = f"📦 *All Orders* (စုစုပေါင်း {total} ခု — page {page + 1})\n\n"
    text += "\n─────────────────────\n".join(
        _format_order_summary(o, skip + i + 1, detailed=True) for i, o in enumerate(orders)
    )

    keyboard = _paginate_keyboard(page, total, ORDERS_PER_PAGE, "allorders_page")

    # Send with pagination buttons; chunk if too long
    chunks = _chunk_text(text, 4000)
    for idx, chunk in enumerate(chunks):
        markup = keyboard if idx == len(chunks) - 1 else None
        await send_fn(chunk, parse_mode="Markdown", reply_markup=markup)


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


async def show_audit_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    📋 Audit Log — shows recent APPROVED and REJECTED orders with who acted on them.
    Useful for accounting and auditing purposes.
    """
    tg_user = update.effective_user
    if not _require_admin(tg_user.id):
        await update.message.reply_text("🚫 Admin only.")
        return

    orders = get_audit_log(limit=20)
    if not orders:
        await update.message.reply_text("📋 Audit log မရှိသေးပါ။")
        return

    lines = [f"📋 *Audit Log — စစ်ဆေးမှတ်တမ်း (နောက်ဆုံး {len(orders)} ခု)*\n"]
    for i, o in enumerate(orders, 1):
        status = o.get("status", "—")
        icon = _status_icon(status)
        actor_id = o.get("approvedBy") or o.get("rejectedBy")
        action_time = _fmt_dt(o.get("approvedAt") or o.get("rejectedAt"))
        action_label = "Approved by" if status == OrderStatus.APPROVED else "Rejected by"
        reason = f"\n   📝 {o['rejectionReason']}" if o.get("rejectionReason") else ""

        lines.append(
            f"{i}. {icon} `{o['orderCode']}`\n"
            f"   User: `{o['telegramUserId']}`\n"
            f"   {format_price(o['amount'])} ({o.get('paymentMethod','—')})\n"
            f"   {action_label}: `{actor_id}` — {action_time}{reason}"
        )

    text = "\n─────────────\n".join(lines)
    await _send_long_message(update.message.reply_text, text)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _chunk_text(text: str, limit: int = 4000) -> list[str]:
    """Split text into Telegram-safe chunks."""
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        # Try to split at a newline boundary
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


async def _send_long_message(send_fn, text: str) -> None:
    """Send a message, splitting into chunks if it exceeds Telegram's 4096 limit."""
    for chunk in _chunk_text(text, 4000):
        await send_fn(chunk, parse_mode="Markdown")


def register(app: Application) -> None:
    app.add_handler(MessageHandler(filters.Text(["🔔 Pending Orders"]), show_pending_orders))
    app.add_handler(MessageHandler(filters.Text(["📦 All Orders"]), show_all_orders))
    app.add_handler(MessageHandler(filters.Text(["📊 Statistics"]), show_statistics))
    app.add_handler(MessageHandler(filters.Text(["📋 Audit Log"]), show_audit_log))
    app.add_handler(CallbackQueryHandler(paginate_all_orders, pattern=r"^allorders_page:\d+$"))
