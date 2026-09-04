"""
app/services/notification_service.py
======================================
Sends notifications to admins and customers.

KEY DESIGN: Telegram file_id from one bot CANNOT be used by another bot.
When a customer uploads a screenshot to the Customer Bot, we:
  1. Download the file bytes using the Customer Bot's token
  2. Re-upload it via the Admin Bot to each admin's chat

This avoids permanent file storage while correctly transferring the image.
"""

from __future__ import annotations

import logging
from io import BytesIO

import httpx
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from app.config import get_settings

logger = logging.getLogger(__name__)


async def _download_file_bytes(customer_bot: Bot, file_id: str) -> bytes | None:
    """
    Download a file from Telegram using the Customer Bot.
    Returns raw bytes or None on failure.
    """
    try:
        tg_file = await customer_bot.get_file(file_id)
        # tg_file.file_path is a temporary HTTPS URL valid for ~1 hour
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(tg_file.file_path)
            response.raise_for_status()
            return response.content
    except TelegramError as e:
        logger.error("Failed to get_file from Telegram: %s", e)
        return None
    except httpx.HTTPError as e:
        logger.error("Failed to download file bytes: %s", e)
        return None


async def notify_admins_new_order(
    customer_bot: Bot,
    admin_bot: Bot,
    order: dict,
    customer: dict,
) -> None:
    """
    Send a new pending order notification to all admins.
    Re-uploads the screenshot from Customer Bot → Admin Bot.
    """
    settings = get_settings()
    admin_ids = settings.admin_telegram_ids

    order_code = order.get("orderCode", "N/A")
    amount = order.get("amount", 0)
    quantity = order.get("quantity", 0)
    payment_method = order.get("paymentMethod", "N/A")
    file_id = order.get("paymentScreenshotFileId")

    movies_text = "\n".join(
        f"  {i+1}. {m.get('title', '?')}"
        for i, m in enumerate(order.get("selectedMovies", []))
    )

    customer_name = customer.get("firstName", "") + " " + customer.get("lastName", "")
    customer_name = customer_name.strip() or "Unknown"
    customer_username = customer.get("username", "")
    customer_telegram_id = customer.get("telegramId", "")

    from datetime import timezone
    created_at = order.get("createdAt")
    created_str = created_at.strftime("%Y-%m-%d %H:%M UTC") if created_at else "N/A"

    text = (
        f"🔔 <b>New Order — {order_code}</b>\n\n"
        f"👤 <b>Customer:</b> {customer_name}\n"
        f"🆔 <b>Username:</b> {'@' + customer_username if customer_username else 'N/A'}\n"
        f"📟 <b>Telegram ID:</b> <code>{customer_telegram_id}</code>\n\n"
        f"🎬 <b>ရွေးချယ်ထားသောကားများ ({quantity}):</b>\n{movies_text}\n\n"
        f"💰 <b>ကျသင့်ငွေ:</b> {amount:,} MMK\n"
        f"💳 <b>ငွေပေးချေမှု:</b> {payment_method}\n"
        f"📅 <b>Order Date:</b> {created_str}\n\n"
        f"📸 Payment Screenshot ကို အောက်တွင် စစ်ဆေးပါ။"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve:{order_code}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject:{order_code}"),
        ]
    ])

    # Download screenshot once using customer bot
    image_bytes: bytes | None = None
    if file_id:
        image_bytes = await _download_file_bytes(customer_bot, file_id)
        if not image_bytes:
            logger.warning("Could not download screenshot for order %s.", order_code)

    for admin_id in admin_ids:
        try:
            if image_bytes:
                await admin_bot.send_photo(
                    chat_id=admin_id,
                    photo=BytesIO(image_bytes),
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
            else:
                # Screenshot unavailable — send text only
                await admin_bot.send_message(
                    chat_id=admin_id,
                    text=text + "\n\n⚠️ Screenshot မရရှိနိုင်ပါ။",
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
        except TelegramError as e:
            logger.error("Failed to notify admin %d: %s", admin_id, e)


async def notify_customer_approved(
    customer_bot: Bot,
    telegram_user_id: int,
    order: dict,
) -> None:
    """Send approval notification with VIP channel links to customer."""
    order_code = order.get("orderCode", "N/A")
    selected_movies = order.get("selectedMovies", [])

    text = (
        f"✅ <b>Payment အတည်ပြုပြီးပါပြီ။</b>\n\n"
        f"🎉 Order <b>{order_code}</b> အတွက် ကျေးဇူးတင်ပါသည်။\n\n"
        f"အောက်ပါ ခလုတ်များကို နှိပ်၍ VIP Channel များသို့ ဝင်ရောက်နိုင်ပါသည်။"
    )

    buttons = [
        [InlineKeyboardButton(
            f"🎬 {m.get('title', 'Movie')} ဝင်ရန်",
            url=m.get("channelLink", "#"),
        )]
        for m in selected_movies
        if m.get("channelLink")
    ]

    try:
        await customer_bot.send_message(
            chat_id=telegram_user_id,
            text=text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
        )
    except TelegramError as e:
        logger.error("Failed to notify customer %d of approval: %s", telegram_user_id, e)


async def notify_customer_rejected(
    customer_bot: Bot,
    telegram_user_id: int,
    order: dict,
) -> None:
    """Send rejection notification with reason to customer."""
    order_code = order.get("orderCode", "N/A")
    reason = order.get("rejectionReason", "အကြောင်းရင်း မဖော်ပြပါ။")

    text = (
        f"❌ <b>Payment အတည်ပြု၍မရပါ။</b>\n\n"
        f"Order: <b>{order_code}</b>\n\n"
        f"<b>အကြောင်းရင်း:</b>\n{reason}\n\n"
        f"ပြဿနာရှိပါက Admin ကို ဆက်သွယ်ပါ သို့မဟုတ် ပြန်လည်ကြိုးစားပါ။"
    )

    try:
        await customer_bot.send_message(
            chat_id=telegram_user_id,
            text=text,
            parse_mode="HTML",
        )
    except TelegramError as e:
        logger.error("Failed to notify customer %d of rejection: %s", telegram_user_id, e)
