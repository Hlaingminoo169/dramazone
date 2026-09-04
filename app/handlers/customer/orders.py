"""
app/handlers/customer/orders.py
=================================
Order history and contact admin handlers.
"""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.config import get_settings
from app.database.mongodb import get_db
from app.services.order_service import get_user_orders
from app.types import OrderStatus

logger = logging.getLogger(__name__)

STATUS_LABELS = {
    OrderStatus.PENDING_PAYMENT.value: "⏳ ငွေပေးချေစောင့်ဆိုင်းနေသည်",
    OrderStatus.WAITING_APPROVAL.value: "🔍 စစ်ဆေးနေဆဲ",
    OrderStatus.APPROVED.value: "✅ အတည်ပြုပြီး",
    OrderStatus.REJECTED.value: "❌ ငြင်းပယ်ခဲ့သည်",
    OrderStatus.CANCELLED.value: "🚫 ပယ်ဖျက်ခဲ့သည်",
}


async def show_order_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show customer's own order history — newest first."""
    user = update.effective_user
    db = get_db()

    orders = get_user_orders(db, user.id, limit=10)

    if not orders:
        text = (
            "📦 <b>ကျွန်ုပ်၏ Order များ</b>\n\n"
            "Order မှတ်တမ်း မရှိသေးပါ။\n"
            "🎬 VIP ကားဝယ်ရန် ပထမဆုံး order တင်ပါ။"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🎬 VIP ကားဝယ်မည်", callback_data="menu:buy")
        ]])
        query = update.callback_query
        if query:
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
        return

    lines = ["📦 <b>ကျွန်ုပ်၏ Order များ</b>\n"]

    for order in orders:
        order_code = order.get("orderCode", "N/A")
        status = order.get("status", "")
        status_label = STATUS_LABELS.get(status, status)
        amount = order.get("amount", 0)
        quantity = order.get("quantity", 0)
        payment_method = order.get("paymentMethod") or "N/A"
        created_at = order.get("createdAt")
        date_str = created_at.strftime("%Y-%m-%d") if created_at else "N/A"

        movie_titles = ", ".join(
            m.get("title", "?")[:20] for m in order.get("selectedMovies", [])
        )

        block = (
            f"━━━━━━━━━━━━━━━━\n"
            f"🆔 <b>{order_code}</b>\n"
            f"📅 {date_str}\n"
            f"🎬 {movie_titles}\n"
            f"🎯 {quantity} ကား | 💰 {amount:,} MMK\n"
            f"💳 {payment_method}\n"
            f"📊 {status_label}"
        )

        if status == OrderStatus.REJECTED.value:
            reason = order.get("rejectionReason", "")
            if reason:
                block += f"\n💬 <i>{reason}</i>"

        lines.append(block)

    text = "\n".join(lines)

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🏠 မူလစာမျက်နှာ", callback_data="menu:home")
    ]])

    query = update.callback_query
    if query:
        await query.answer()
        try:
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
        except Exception:
            await query.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the admin contact link."""
    settings = get_settings()
    admin_username = settings.admin_username

    text = (
        f"📞 <b>Admin ကို ဆက်သွယ်မည်</b>\n\n"
        f"မေးခွန်းများ သို့မဟုတ် အကူအညီလိုအပ်ပါက:\n\n"
        f"👉 @{admin_username} သို့ တိုက်ရိုက်ဆက်သွယ်နိုင်ပါသည်။"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💬 @{admin_username} နှင့် ဆက်သွယ်မည်",
                              url=f"https://t.me/{admin_username}")],
        [InlineKeyboardButton("🏠 မူလစာမျက်နှာ", callback_data="menu:home")],
    ])

    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
