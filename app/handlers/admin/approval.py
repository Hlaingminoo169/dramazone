"""
app/handlers/admin/approval.py

Admin approve/reject order handlers — Steps 14 & 15.

Atomic state transitions prevent duplicate approve/reject.
"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from app.config import settings
from app.services.notification_service import (
    CB_APPROVE,
    CB_REJECT,
    notify_customer_approved,
    notify_customer_rejected,
)
from app.services.order_service import approve_order, reject_order, get_order_by_id
from app.services.session_service import (
    get_session,
    set_session,
    clear_session,
    get_session_state,
)
from app.types import BotType, SessionState

logger = logging.getLogger(__name__)


def _is_admin(tg_id: int) -> bool:
    return settings.is_admin(tg_id)


async def handle_approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Admin clicks ✅ Approve.

    Atomic: only succeeds if order is still WAITING_APPROVAL.
    """
    query = update.callback_query
    await query.answer()
    admin_id = update.effective_user.id

    if not _is_admin(admin_id):
        await query.answer("🚫 Admin only.", show_alert=True)
        return

    order_id = query.data.split(":")[1] if ":" in query.data else None
    if not order_id:
        await query.edit_message_caption(caption="❌ Invalid order ID.")
        return

    # Atomic approval.
    updated = approve_order(order_id, admin_id)
    if not updated:
        # Could be already processed.
        order = get_order_by_id(order_id)
        if order:
            await query.answer(
                f"⚠️ Order သည် ဤ status ဖြင့် ရှိနှင့်ပြီးဖြစ်သည်: {order['status']}",
                show_alert=True,
            )
        else:
            await query.answer("⚠️ Order မတွေ့ပါ။", show_alert=True)
        return

    # Edit the admin notification message to reflect approval.
    try:
        await query.edit_message_caption(
            caption=(
                f"✅ *Approved*\n\n"
                f"Order: `{updated['orderCode']}`\n"
                f"Approved by: Admin `{admin_id}`"
            ),
            parse_mode="Markdown",
        )
    except Exception:
        pass  # Message may not have a caption if it was text-only.

    # Notify customer.
    try:
        from app.bots.customer_bot import get_customer_app
        await notify_customer_approved(
            customer_bot=get_customer_app().bot,
            telegram_user_id=updated["telegramUserId"],
            order=updated,
        )
    except Exception as exc:
        logger.error("Failed to notify customer after approval: %s", exc)


async def handle_reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Admin clicks ❌ Reject.

    Stores order_id in admin session and asks for rejection reason.
    """
    query = update.callback_query
    await query.answer()
    admin_id = update.effective_user.id

    if not _is_admin(admin_id):
        await query.answer("🚫 Admin only.", show_alert=True)
        return

    order_id = query.data.split(":")[1] if ":" in query.data else None
    if not order_id:
        return

    # Verify the order is still in a reject-able state.
    order = get_order_by_id(order_id)
    if not order:
        await query.answer("⚠️ Order မတွေ့ပါ။", show_alert=True)
        return
    if order["status"] != "WAITING_APPROVAL":
        await query.answer(
            f"⚠️ Order ကို ယခု ငြင်းမပယ်နိုင်ပါ။ (Status: {order['status']})",
            show_alert=True,
        )
        return

    # Store order_id in admin session, await reason text.
    set_session(
        admin_id,
        BotType.ADMIN,
        SessionState.WAITING_FOR_REJECTION_REASON,
        data={"orderId": order_id},
    )

    await query.message.reply_text(
        f"❌ *Reject လုပ်ရသည့်အကြောင်းရင်းကို ရိုက်ထည့်ပါ။*\n\n"
        f"Order: `{order['orderCode']}`",
        parse_mode="Markdown",
    )


async def handle_rejection_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Admin types the rejection reason.

    Triggered when admin is in WAITING_FOR_REJECTION_REASON state.
    """
    admin_id = update.effective_user.id

    if not _is_admin(admin_id):
        return

    if get_session_state(admin_id, BotType.ADMIN) != SessionState.WAITING_FOR_REJECTION_REASON:
        return

    session = get_session(admin_id, BotType.ADMIN)
    order_id = session.get("data", {}).get("orderId")
    reason = update.message.text.strip()

    if not reason:
        await update.message.reply_text("⚠️ အကြောင်းရင်းထည့်ပေးပါ။")
        return

    if not order_id:
        await update.message.reply_text("⚠️ Order ID မတွေ့ပါ။ /start ကိုနှိပ်ပါ။")
        clear_session(admin_id, BotType.ADMIN)
        return

    # Atomic rejection.
    updated = reject_order(order_id, admin_id, reason)
    if not updated:
        order = get_order_by_id(order_id)
        if order:
            await update.message.reply_text(
                f"⚠️ ငြင်းပယ်မှု မအောင်မြင်ပါ။ Order status: {order['status']}"
            )
        else:
            await update.message.reply_text("⚠️ Order မတွေ့ပါ။")
        clear_session(admin_id, BotType.ADMIN)
        return

    clear_session(admin_id, BotType.ADMIN)

    await update.message.reply_text(
        f"✅ Order `{updated['orderCode']}` ကို ငြင်းပယ်ပြီးပါပြီ။",
        parse_mode="Markdown",
    )

    # Notify customer.
    try:
        from app.bots.customer_bot import get_customer_app
        await notify_customer_rejected(
            customer_bot=get_customer_app().bot,
            telegram_user_id=updated["telegramUserId"],
            order=updated,
        )
    except Exception as exc:
        logger.error("Failed to notify customer after rejection: %s", exc)


def register(app: Application) -> None:
    app.add_handler(CallbackQueryHandler(handle_approve_callback, pattern=f"^{CB_APPROVE}:"))
    app.add_handler(CallbackQueryHandler(handle_reject_callback, pattern=f"^{CB_REJECT}:"))
    # Text handler for rejection reason — must be lower priority than other text handlers.
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_rejection_reason,
        ),
        group=1,  # Lower priority group
    )
