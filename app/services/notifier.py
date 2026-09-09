"""
app/services/notifier.py
────────────────────────────────────────────────────────────────────────
Cross-bot Notifier Service.

Handles:
- Broadcasting new order alerts with screenshot photo & action buttons to all Admins.
- Delivering VIP Watch Links to Customer upon Order Approval.
- Delivering Rejection Notice to Customer upon Order Rejection.
"""

import logging
from typing import List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import config
from app.models.order import Order
from app.models.movie import Movie

logger = logging.getLogger("dramazone.services.notifier")


class NotifierService:
    """Service to handle Telegram notifications between Customer and Admin bots."""

    async def notify_admins_new_order(
        self,
        order: Order,
        screenshot_file_id: str,
        user_info: dict,
        selected_movies: List[Movie]
    ) -> None:
        """
        Send photo message to all configured Admin Telegram IDs when a customer submits proof.
        """
        from app.bot.admin.bot import admin_bot_app
        if not admin_bot_app or not admin_bot_app.bot:
            logger.warning("Admin bot application not initialized. Cannot send admin notification.")
            return

        admin_ids = config.admin_ids
        if not admin_ids:
            logger.warning("No ADMIN_TELEGRAM_IDS configured in environment.")
            return

        movie_titles = "\n".join([f"• {m.title or m.titleEn}" for m in selected_movies])
        username_str = f"@{user_info.get('username')}" if user_info.get('username') else "မရှိပါ"
        name_str = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()

        caption = (
            f"🔔 **အော်ဒါအသစ် ရောက်ရှိပါသည်!**\n\n"
            f"• Order Code: **#{order.orderCode}**\n"
            f"• Customer: **{name_str}** ({username_str})\n"
            f"• Telegram ID: `{order.telegramUserId}`\n"
            f"• ဇာတ်ကား အရေအတွက်: **{order.packageSize} ကား**\n"
            f"• ကျသင့်ငွေ: **{order.totalAmount:,} MMK**\n"
            f"• Payment Method: **{(order.paymentMethod or 'N/A').upper()}**\n\n"
            f"🎬 **ရွေးချယ်ထားသော ဇာတ်ကားများ:**\n{movie_titles}\n\n"
            f"ကျေးဇူးပြု၍ ငွေလွှဲပြေစာကို စစ်ဆေး၍ အောက်ပါ Button များကို နှိပ်ပါ။"
        )

        keyboard = [
            [
                InlineKeyboardButton("✅ Approve (အတည်ပြုမည်)", callback_data=f"admin_approve:{order.orderCode}"),
                InlineKeyboardButton("❌ Reject (ငြင်းပယ်မည်)", callback_data=f"admin_reject:{order.orderCode}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        for admin_id in admin_ids:
            try:
                await admin_bot_app.bot.send_photo(
                    chat_id=admin_id,
                    photo=screenshot_file_id,
                    caption=caption,
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
                logger.info(f"Sent order #{order.orderCode} notification to admin ID {admin_id}")
            except Exception as e:
                logger.error(f"Failed to send admin notification to {admin_id}: {str(e)}")

    async def notify_customer_order_approved(
        self,
        order: Order,
        movies: List[Movie]
    ) -> bool:
        """
        Send approval message + VIP Watch Links to customer on Customer Bot.
        """
        from app.bot.customer.bot import customer_bot_app
        if not customer_bot_app or not customer_bot_app.bot:
            logger.warning("Customer bot application not initialized. Cannot send customer notification.")
            return False

        links_text = ""
        for idx, m in enumerate(movies, 1):
            title = m.title or m.titleEn
            link = m.watchLink or "Link ဖြည့်သွင်းထားခြင်း မရှိပါ"
            links_text += f"{idx}. **{title}**\n👉 [ဇာတ်ကား ကြည့်ရန် နှိပ်ပါ]({link})\n\n"

        text = (
            f"🎉 **အော်ဒါ အတည်ပြုပြီးပါပြီ!**\n\n"
            f"လူကြီးမင်း ဝယ်ယူထားသော Order **#{order.orderCode}** အတွက် ငွေလွှဲပြေစာ စစ်ဆေးပြီးပါပြီ။\n\n"
            f"🎬 **ဇာတ်ကား ကြည့်ရှုရန် Link များ:**\n\n"
            f"{links_text}"
            f"ဝယ်ယူအားပေးမှုကို ကျေးဇူးအထူးတင်ရှိပါသည်။ ရသစုံ လွတ်လပ်စွာ ခံစားကြည့်ရှုနိုင်ပါပြီ။ ✨\n\n"
            f"• ဝယ်ယူခဲ့သော ဇာတ်ကားများကို /orders တွင်လည်း ပြန်လည်ကြည့်ရှုနိုင်ပါသည်။"
        )

        try:
            await customer_bot_app.bot.send_message(
                chat_id=order.telegramUserId,
                text=text,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            logger.info(f"Sent approval notification & links for order #{order.orderCode} to customer {order.telegramUserId}")
            return True
        except Exception as e:
            logger.error(f"Failed to notify customer {order.telegramUserId} of approval: {str(e)}")
            return False

    async def notify_customer_order_rejected(
        self,
        order: Order,
        reason: str
    ) -> bool:
        """
        Send rejection message to customer on Customer Bot.
        """
        from app.bot.customer.bot import customer_bot_app
        if not customer_bot_app or not customer_bot_app.bot:
            logger.warning("Customer bot application not initialized. Cannot send customer rejection.")
            return False

        text = (
            f"❌ **အော်ဒါ ငြင်းပယ်ခံရပါသည် (Order Rejected)**\n\n"
            f"လူကြီးမင်း၏ Order **#{order.orderCode}** အား အောက်ပါ အကြောင်းအရင်းကြောင့် အတည်မပြုနိုင်ပါ သို့မဟုတ် ငြင်းပယ်လိုက်ပါသည်။\n\n"
            f"• **အကြောင်းအရင်း:** {reason}\n\n"
            f"ကျေးဇူးပြု၍ /start ဖြင့် ပြန်လည် ရွေးချယ် ဝယ်ယူနိုင်ပါသည်။ သံသယရှိပါက အကူအညီရယူရန် Admin ထံ ဆက်သွယ်ပါ။"
        )

        try:
            await customer_bot_app.bot.send_message(
                chat_id=order.telegramUserId,
                text=text,
                parse_mode="Markdown"
            )
            logger.info(f"Sent rejection notification for order #{order.orderCode} to customer {order.telegramUserId}")
            return True
        except Exception as e:
            logger.error(f"Failed to notify customer {order.telegramUserId} of rejection: {str(e)}")
            return False


notifier_service = NotifierService()
