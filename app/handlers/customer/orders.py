"""
app/handlers/customer/orders.py

Order history handler — Step 16.
Contact admin handler — Step 17.
"""
from __future__ import annotations

import logging
from datetime import timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from app.config import settings
from app.services.order_service import get_orders_for_user, count_orders_for_user
from app.types import OrderStatus
from app.utils.pricing import format_price

logger = logging.getLogger(__name__)

PAGE_SIZE = 5
CB_ORDER_PAGE = "ord_page"


def _status_label(status: str) -> str:
    labels = {
        OrderStatus.PENDING_PAYMENT: "⏳ ငွေပေးချေစောင့်",
        OrderStatus.WAITING_APPROVAL: "🔍 စစ်ဆေးနေ",
        OrderStatus.APPROVED: "✅ အတည်ပြုပြီး",
        OrderStatus.REJECTED: "❌ ငြင်းပယ်ပြီး",
        OrderStatus.CANCELLED: "🚫 ပယ်ဖျက်ပြီး",
    }
    return labels.get(status, status)


def _format_order(order: dict, index: int) -> str:
    """Format a single order for display."""
    movies = order.get("selectedMovies", [])
    movie_list = "\n".join(f"    • {m['title']}" for m in movies)

    # Format date in UTC.
    created = order.get("createdAt")
    date_str = created.strftime("%Y-%m-%d %H:%M") if created else "—"

    text = (
        f"━━━━━━━━━━━━━━━━━\n"
        f"*Order {index}*\n"
        f"ID: `{order['orderCode']}`\n"
        f"ရက်: {date_str}\n"
        f"ကားများ:\n{movie_list}\n"
        f"အရေအတွက်: {order['quantity']}\n"
        f"ငွေပမာဏ: {format_price(order['amount'])}\n"
        f"ပေးချေမှု: {order['paymentMethod']}\n"
        f"Status: {_status_label(order['status'])}"
    )

    if order["status"] == OrderStatus.REJECTED and order.get("rejectionReason"):
        text += f"\nအကြောင်းရင်း: {order['rejectionReason']}"

    return text


async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the user's order history (first page)."""
    from app.handlers.customer.start import BTN_ORDERS

    if update.message and update.message.text != BTN_ORDERS:
        return

    tg_user = update.effective_user
    await _send_orders_page(update, context, tg_user.id, page=0)


async def handle_order_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle pagination callbacks."""
    query = update.callback_query
    await query.answer()
    tg_user = update.effective_user

    try:
        page = int(query.data.split(":")[1])
    except (IndexError, ValueError):
        return

    await _send_orders_page(update, context, tg_user.id, page=page, edit=True)


async def _send_orders_page(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    telegram_user_id: int,
    page: int,
    edit: bool = False,
) -> None:
    total = count_orders_for_user(telegram_user_id)

    if total == 0:
        text = "📦 *ကျွန်ုပ်၏ Orders*\n\nOrder တစ်ခုမှ မရှိသေးပါ။"
        if edit:
            await update.callback_query.edit_message_text(text, parse_mode="Markdown")
        else:
            await update.message.reply_text(text, parse_mode="Markdown")
        return

    orders = get_orders_for_user(telegram_user_id, limit=PAGE_SIZE, skip=page * PAGE_SIZE)
    if not orders:
        await (update.callback_query or update).answer("နောက်ထပ် Order မရှိပါ။", show_alert=True)
        return

    header = f"📦 *ကျွန်ုပ်၏ Orders* ({total} ခု)\n"
    body = "\n".join(
        _format_order(order, page * PAGE_SIZE + i + 1)
        for i, order in enumerate(orders)
    )
    text = header + body

    # Pagination buttons.
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton("⬅️ ယခင်", callback_data=f"{CB_ORDER_PAGE}:{page - 1}")
        )
    if (page + 1) * PAGE_SIZE < total:
        nav_buttons.append(
            InlineKeyboardButton("➡️ နောက်", callback_data=f"{CB_ORDER_PAGE}:{page + 1}")
        )

    keyboard = InlineKeyboardMarkup([nav_buttons]) if nav_buttons else None

    if edit:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=keyboard
        )
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


# ── Contact admin (Step 17) ──────────────────────────────────────────────────
async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Provide admin contact link."""
    from app.handlers.customer.start import BTN_CONTACT

    if update.message and update.message.text != BTN_CONTACT:
        return

    admin_username = settings.admin_username
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💬 @{admin_username}", url=f"https://t.me/{admin_username}")]
    ])
    await update.message.reply_text(
        "📞 *Admin ကို ဆက်သွယ်မည်*\n\nအောက်ပါ Link မှ Admin ကို တိုက်ရိုက်ဆက်သွယ်နိုင်ပါသည်။",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


def register(app: Application) -> None:
    """Register order history and contact handlers."""
    from app.handlers.customer.start import BTN_ORDERS, BTN_CONTACT

    app.add_handler(MessageHandler(filters.Text([BTN_ORDERS]), show_orders))
    app.add_handler(MessageHandler(filters.Text([BTN_CONTACT]), contact_admin))
    app.add_handler(CallbackQueryHandler(handle_order_page_callback, pattern=f"^{CB_ORDER_PAGE}:"))
