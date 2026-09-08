"""
app/services/notification_service.py

Sends Telegram messages to customers and admins.

Important — File transfer between bots:
  The Customer Bot and Admin Bot are separate Telegram identities.
  A file_id received by the Customer Bot CANNOT be directly used by
  the Admin Bot (Telegram does not allow cross-bot file sharing).

  Strategy implemented here:
  1. Customer Bot forwards the photo to a temporary message sent to itself.
  2. The raw file content is forwarded to each admin via the Admin Bot.
  3. No files are written to local disk permanently.
  4. The Admin Bot re-uploads the bytes to Telegram (which assigns a new file_id).
"""
from __future__ import annotations

import logging
import os
import tempfile
from typing import List

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from app.config import settings
from app.utils.pricing import format_price

logger = logging.getLogger(__name__)

# ── Callback data prefixes ────────────────────────────────────────────────────
CB_APPROVE = "approve"
CB_REJECT = "reject"


def _build_approve_reject_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Build inline keyboard with Approve / Reject buttons."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"{CB_APPROVE}:{order_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"{CB_REJECT}:{order_id}"),
        ]
    ])


def format_admin_order_notification(
    order: dict,
    user: dict,
    status: str = "WAITING_APPROVAL",
    admin_display: str | None = None,
    rejection_reason: str | None = None,
) -> str:
    """
    Format the admin notification message for an order status.

    Includes customer profile link, telegram username, and (when processed)
    which admin approved/rejected the payment along with the action timestamp.
    """
    from datetime import datetime, timezone, timedelta

    def _fmt_mmt(dt) -> str:
        """Convert UTC datetime to Myanmar Time (UTC+6:30) string."""
        if not dt:
            return "—"
        if isinstance(dt, datetime) and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        mmt = dt + timedelta(hours=6, minutes=30)
        return mmt.strftime("%Y-%m-%d %H:%M (MMT)")

    movies_text = "\n".join(
        f"  {i + 1}. {m['title']}"
        for i, m in enumerate(order.get("selectedMovies", []))
    )
    username = user.get("username") if user else None
    username_display = f"@{username}" if username else "(username မရှိပါ)"
    first_name = user.get("firstName", "") if user else ""
    last_name = user.get("lastName", "") if user else ""
    full_name = f"{first_name} {last_name}".strip() or "(နာမည်မရှိပါ)"
    clean_name = full_name.replace("[", "(").replace("]", ")")
    tg_id = order.get("telegramUserId")

    created_str = _fmt_mmt(order.get("createdAt"))

    if status == "APPROVED":
        header = "✅ *Payment Approved*"
        status_str = "✅ `APPROVED`"
    elif status == "REJECTED":
        header = "❌ *Payment Rejected*"
        status_str = "❌ `REJECTED`"
    else:
        header = "🔔 *New Payment Received*"
        status_str = "⏳ `WAITING_APPROVAL`"

    lines = [
        f"{header}\n",
        f"Order ID: `{order['orderCode']}`",
        f"Customer: [{clean_name}](tg://user?id={tg_id})",
        f"Username: {username_display}",
        f"Telegram ID: `{tg_id}`\n",
        f"Movies:\n{movies_text}\n",
        f"Quantity: {order['quantity']}",
        f"Amount: *{format_price(order['amount'])}*",
        f"Payment Method: {order['paymentMethod']}",
        f"Order Date: {created_str}\n",
        f"Status: {status_str}",
    ]

    if admin_display:
        if status == "APPROVED":
            action_time = _fmt_mmt(order.get("approvedAt"))
            lines.append(f"✅ Approved by: {admin_display}")
            lines.append(f"🕐 Approved at: {action_time}")
        elif status == "REJECTED":
            action_time = _fmt_mmt(order.get("rejectedAt"))
            lines.append(f"❌ Rejected by: {admin_display}")
            lines.append(f"🕐 Rejected at: {action_time}")

    if rejection_reason and status == "REJECTED":
        lines.append(f"📝 Reason: {rejection_reason}")

    return "\n".join(lines)


async def notify_admins_new_payment(
    order: dict,
    user: dict,
    screenshot_file_id: str,
    customer_bot: Bot,
    admin_bot: Bot,
) -> None:
    """
    Notify all admins of a new payment submission.

    Downloads the screenshot via the Customer Bot and re-uploads it
    via the Admin Bot to avoid cross-bot file ID restrictions.
    """
    order_id = str(order["_id"])
    caption = format_admin_order_notification(order, user, status="WAITING_APPROVAL")
    keyboard = _build_approve_reject_keyboard(order_id)

    # ── Download screenshot from Telegram via Customer Bot ────────────────────
    photo_bytes: bytes | None = None
    try:
        file_obj = await customer_bot.get_file(screenshot_file_id)
        # Download to an in-memory bytes buffer.
        photo_bytes = await file_obj.download_as_bytearray()
    except TelegramError as exc:
        logger.error("Failed to download screenshot %s: %s", screenshot_file_id, exc)

    # ── Send to each admin via Admin Bot ──────────────────────────────────────
    for admin_id in settings.admin_ids:
        try:
            if photo_bytes:
                await admin_bot.send_photo(
                    chat_id=admin_id,
                    photo=bytes(photo_bytes),
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
            else:
                # Fallback: send text only if download failed.
                await admin_bot.send_message(
                    chat_id=admin_id,
                    text=caption + "\n\n⚠️ Screenshot ပေးပို့မှုမအောင်မြင်ပါ။",
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
            logger.info("Admin %s notified of order %s", admin_id, order["orderCode"])
        except TelegramError as exc:
            logger.error("Failed to notify admin %s: %s", admin_id, exc)


async def notify_customer_approved(
    customer_bot: Bot,
    telegram_user_id: int,
    order: dict,
) -> None:
    """
    Notify the customer that their order was approved.
    Includes inline URL buttons for each purchased channel.
    """
    movies = order.get("selectedMovies", [])
    buttons = [
        [InlineKeyboardButton(f"🎬 {m['title']}", url=m["channelLink"])]
        for m in movies
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    text = (
        f"✅ *Payment အတည်ပြုပြီးပါပြီ။*\n\n"
        f"Order ID: `{order['orderCode']}`\n\n"
        f"သင်ဝယ်ယူထားသော VIP Content များကို အောက်ပါ Link များမှ ဝင်ရောက်နိုင်ပါသည်။\n\n"
        f"⚠️ Link များကို သိမ်းဆည်းထားပါ။ ကာကွယ်ရေးအတွက် အများနှင့် မမျှဝေပါနှင့်။"
    )

    try:
        await customer_bot.send_message(
            chat_id=telegram_user_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    except TelegramError as exc:
        logger.error(
            "Failed to send approval notification to user %s: %s",
            telegram_user_id, exc,
        )


async def notify_customer_rejected(
    customer_bot: Bot,
    telegram_user_id: int,
    order: dict,
) -> None:
    """Notify the customer that their payment was rejected."""
    reason = order.get("rejectionReason") or "အကြောင်းရင်းမဖော်ပြပါ။"
    text = (
        f"❌ *Payment အတည်ပြု၍မရပါ။*\n\n"
        f"Order ID: `{order['orderCode']}`\n\n"
        f"အကြောင်းရင်း:\n{reason}\n\n"
        f"ပြန်လည်ကြိုးစားရန် /start ကိုနှိပ်ပါ။"
    )
    try:
        await customer_bot.send_message(
            chat_id=telegram_user_id,
            text=text,
            parse_mode="Markdown",
        )
    except TelegramError as exc:
        logger.error(
            "Failed to send rejection notification to user %s: %s",
            telegram_user_id, exc,
        )
