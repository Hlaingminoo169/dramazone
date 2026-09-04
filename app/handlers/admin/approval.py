"""
app/handlers/admin/approval.py
================================
Approve and reject order handlers with race-condition protection.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.database.mongodb import get_db
from app.handlers.admin.auth import is_admin, unauthorized_response
from app.services.notification_service import notify_customer_approved, notify_customer_rejected
from app.services.order_service import approve_order, get_order_by_code, reject_order
from app.services.session_service import clear_session, get_session, set_session
from app.types import AdminState, BotType

logger = logging.getLogger(__name__)


async def approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle ✅ Approve button.
    Uses atomic find_one_and_update — safe against two admins approving simultaneously.
    """
    query = update.callback_query
    user = update.effective_user

    if not user or not is_admin(user.id):
        await unauthorized_response(update, context)
        return

    await query.answer()

    # callback_data = "approve:ORD-1234"
    parts = query.data.split(":", 1)
    if len(parts) != 2:
        await query.answer("❌ Invalid callback data.", show_alert=True)
        return

    order_code = parts[1]
    db = get_db()

    success, reason = approve_order(db, order_code, approved_by=user.id)

    if success:
        order = get_order_by_code(db, order_code)
        await query.edit_message_caption(
            caption=(query.message.caption or "") + f"\n\n✅ <b>Approved by @{user.username or user.id}</b>",
            parse_mode="HTML",
        ) if query.message.caption else await query.edit_message_text(
            f"✅ Order <b>{order_code}</b> ကို Approve လုပ်ပြီးပါပြီ။",
            parse_mode="HTML",
        )

        if order:
            from app.bots.customer_bot import get_customer_bot
            customer_bot = get_customer_bot()
            await notify_customer_approved(customer_bot, order["telegramUserId"], order)

    elif reason == "already_processed":
        await query.answer(
            "ဒီ Order ကို အခြား Admin မှ စီမံပြီးပါပြီ။",
            show_alert=True,
        )
    else:
        await query.answer(
            f"❌ Order {order_code} မတွေ့ပါ သို့မဟုတ် စစ်ဆေးနိုင်ခြင်းမရှိပါ။",
            show_alert=True,
        )


async def reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle ❌ Reject button — ask admin for rejection reason.
    Stores pending rejection in admin session.
    """
    query = update.callback_query
    user = update.effective_user

    if not user or not is_admin(user.id):
        await unauthorized_response(update, context)
        return

    await query.answer()

    parts = query.data.split(":", 1)
    if len(parts) != 2:
        await query.answer("❌ Invalid callback data.", show_alert=True)
        return

    order_code = parts[1]
    db = get_db()

    # Store pending rejection in admin session
    set_session(
        db, user.id, BotType.ADMIN,
        state=AdminState.WAITING_FOR_REJECTION_REASON.value,
        data={"pending_rejection_order_code": order_code},
    )

    await query.message.reply_text(
        f"❌ Order <b>{order_code}</b> ကို Reject လုပ်ရသည့်အကြောင်းရင်းကို ရိုက်ထည့်ပါ:",
        parse_mode="HTML",
    )


async def rejection_reason_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle admin text message when WAITING_FOR_REJECTION_REASON.
    Validates order, applies rejection, notifies customer.
    """
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    db = get_db()
    session = get_session(db, user.id, BotType.ADMIN)

    if session.get("state") != AdminState.WAITING_FOR_REJECTION_REASON.value:
        return  # Not in this state — ignore

    session_data = session.get("data", {})
    order_code: str | None = session_data.get("pending_rejection_order_code")

    if not order_code:
        await update.message.reply_text("⚠️ Session ကုန်သွားပါပြီ။ /start နှိပ်ပါ။")
        clear_session(db, user.id, BotType.ADMIN)
        return

    reason = (update.message.text or "").strip()
    if not reason:
        await update.message.reply_text("❌ အကြောင်းရင်း မထည့်ပါ။ ကျေးဇူးပြု၍ ရိုက်ထည့်ပါ။")
        return

    success, msg = reject_order(db, order_code, rejected_by=user.id, reason=reason)

    clear_session(db, user.id, BotType.ADMIN)

    if success:
        order = get_order_by_code(db, order_code)
        await update.message.reply_text(
            f"✅ Order <b>{order_code}</b> ကို Reject လုပ်ပြီးပါပြီ။\n"
            f"အကြောင်းရင်း: {reason}",
            parse_mode="HTML",
        )
        if order:
            from app.bots.customer_bot import get_customer_bot
            customer_bot = get_customer_bot()
            await notify_customer_rejected(customer_bot, order["telegramUserId"], order)

    elif msg == "already_processed":
        await update.message.reply_text(
            f"⚠️ Order <b>{order_code}</b> ကို အခြား Admin မှ စီမံပြီးပါပြီ။",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            f"❌ Order <b>{order_code}</b> မတွေ့ပါ။",
            parse_mode="HTML",
        )
