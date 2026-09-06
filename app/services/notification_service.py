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


def _format_order_notification(order: dict, user: dict) -> str:
    """Format the admin notification message for a new payment."""
    movies_text = "\n".join(
        f"  {i + 1}. {m['title']}"
        for i, m in enumerate(order.get("selectedMovies", []))
    )
    username_display = (
        f"@{user.get('username')}" if user.get("username") else "(username မရှိပါ)"
    )
    first_name = user.get("firstName", "")
    last_name = user.get("lastName", "")
    full_name = f"{first_name} {last_name}".strip() or "(နာမည်မရှိပါ)"

    return (
        f"🔔 *New Payment Received*\n\n"
        f"Order ID: `{order['orderCode']}`\n"
        f"Customer: {full_name}\n"
        f"Username: {username_display}\n"
        f"Telegram ID: `{order['telegramUserId']}`\n\n"
        f"Movies:\n{movies_text}\n\n"
        f"Quantity: {order['quantity']}\n"
        f"Amount: *{format_price(order['amount'])}*\n"
        f"Payment Method: {order['paymentMethod']}\n\n"
        f"Status: WAITING\\_APPROVAL"
    )


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
    caption = _format_order_notification(order, user)
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
