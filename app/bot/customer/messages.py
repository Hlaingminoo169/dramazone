"""
app/bot/customer/messages.py
─────────────────────────────────────────────────────────────────────────────
All Myanmar message strings for the Customer Bot.

Centralised here so:
- Messages are easy to find and edit
- No magic strings scattered across handlers
- Future localisation is trivial
"""
from __future__ import annotations

# ──────────────────────────────────────────────
# Welcome / Main Menu
# ──────────────────────────────────────────────
WELCOME = (
    "မင်္ဂလာပါ 👋\n\n"
    "🎬 <b>DramaZone VIP</b> မှ ကြိုဆိုပါသည်။\n\n"
    "မြန်မာ Drama များကို HD အရည်အသွေးဖြင့် ကြည့်ရှုနိုင်ပါသည်။\n\n"
    "စတင်ဝယ်ယူရန် အောက်မှ ခလုတ်ကို နှိပ်ပါ။"
)

WELCOME_BACK = (
    "မင်္ဂလာပါ 👋\n\n"
    "🎬 <b>DramaZone VIP</b>\n\n"
    "ဘာတွေ ကူညီပေးရမလဲ?"
)

HELP_TEXT = "အကူအညီ လိုအပ်ပါက Admin သို့ ဆက်သွယ်ပါ။"
RATE_LIMIT_EXCEEDED = "⏳ ခဏလောက်စောင့်ပြီး ပြန်လည်ကြိုးစားပေးပါ။"

# ──────────────────────────────────────────────
# Package Selection
# ──────────────────────────────────────────────
INVALID_PACKAGE_SIZE = "❌ ရွေးချယ်မှု မှားယွင်းနေပါသည်။"

SELECT_PACKAGE = (
    "🛒 <b>Package ရွေးချယ်ပါ</b>\n\n"
    "ကြည့်ရှုလိုသော ဇာတ်ကား အရေအတွက်ကို ရွေးချယ်ပါ။"
)

# ──────────────────────────────────────────────
# Movie Selection
# ──────────────────────────────────────────────
def select_movies(package_size: int, selected_count: int) -> str:
    remaining = package_size - selected_count
    if remaining > 0:
        return (
            f"🎬 <b>ဇာတ်ကား ရွေးချယ်ပါ</b>\n\n"
            f"Package: <b>{package_size} ကား</b>\n"
            f"ရွေးချယ်ပြီး: <b>{selected_count} ကား</b>\n"
            f"ကျန်ရှိသော: <b>{remaining} ကား</b>\n\n"
            f"ကြည့်ရှုလိုသော ဇာတ်ကားများကို ✅ နှိပ်ပြီး ရွေးချယ်ပါ။"
        )
    return (
        f"🎬 <b>ဇာတ်ကား ရွေးချယ်ပြီးပါပြီ</b>\n\n"
        f"Package: <b>{package_size} ကား</b>\n"
        f"ရွေးချယ်ပြီး: <b>{selected_count} ကား</b> ✅\n\n"
        f"အောက်မှ <b>အတည်ပြုမည်</b> ကို နှိပ်ပါ။"
    )

# ──────────────────────────────────────────────
# Order Summary
# ──────────────────────────────────────────────
def order_summary(order_code: str, movie_titles: list[str], package_size: int, amount: int) -> str:
    movies_text = "\n".join(f"🎬 {title}" for title in movie_titles)
    amount_formatted = f"{amount:,}"
    return (
        f"🧾 <b>ORDER SUMMARY</b>\n\n"
        f"Order ID:\n"
        f"<code>{order_code}</code>\n\n"
        f"ဝယ်ယူမည့် ဇာတ်ကားများ:\n"
        f"{movies_text}\n\n"
        f"အရေအတွက်: <b>{package_size} ကား</b>\n\n"
        f"ပေးချေရမည့် ပမာဏ:\n"
        f"<b>{amount_formatted} MMK</b>"
    )

# ──────────────────────────────────────────────
# Payment
# ──────────────────────────────────────────────
SELECT_PAYMENT_METHOD = (
    "💳 <b>ငွေပေးချေနည်းကို ရွေးချယ်ပါ</b>"
)


def payment_instructions(
    method_name: str,
    account_name: str,
    phone: str,
    amount: int,
    order_code: str,
) -> str:
    amount_formatted = f"{amount:,}"
    return (
        f"💳 <b>{method_name}</b>\n\n"
        f"အမည်:\n<b>{account_name}</b>\n\n"
        f"ဖုန်းနံပါတ်:\n<b>{phone}</b>\n\n"
        f"ပေးချေရမည့် ပမာဏ:\n<b>{amount_formatted} MMK</b>\n\n"
        f"Order ID:\n<code>{order_code}</code>\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📌 ငွေလွှဲပြီးနောက် Screenshot ပို့ပေးပါ။\n"
        f"Order ID ကို မှတ်သားထားပါ။"
    )


SEND_SCREENSHOT = (
    "📸 <b>Screenshot ပို့ပေးပါ</b>\n\n"
    "ငွေလွှဲပြီးသော Screenshot ကို <b>Photo</b> အဖြစ် ပေးပို့ပေးပါ။"
)

WRONG_FILE_TYPE = (
    "❌ <b>Payment Screenshot မဟုတ်ပါ</b>\n\n"
    "ငွေလွှဲပြီးသော Screenshot ကို <b>Photo</b> အဖြစ် ပြန်လည်ပေးပို့ပေးပါ။\n\n"
    "(File/Document အဖြစ် မပို့ပါနဲ့ — Photo အဖြစ်ပဲ ပို့ပေးပါ)"
)


def screenshot_received(order_code: str) -> str:
    return (
        f"✅ <b>Screenshot လက်ခံရရှိပါပြီ</b>\n\n"
        f"Order ID:\n<code>{order_code}</code>\n\n"
        f"⏳ Admin စစ်ဆေးနေပါသည်။\n"
        f"အတည်ပြုပြီးပါက ချက်ချင်း အသိပေးပါမည်။"
    )


SCREENSHOT_ALREADY_SUBMITTED = (
    "ℹ️ ဒီ Order အတွက် Screenshot ရရှိပြီး ဖြစ်ပါတယ်။\n\n"
    "⏳ Admin စစ်ဆေးနေပါသည်။ ခဏစောင့်ပေးပါ။"
)

# ──────────────────────────────────────────────
# Order Status Labels (req #26)
# ──────────────────────────────────────────────
STATUS_LABELS: dict[str, str] = {
    "PENDING_PAYMENT":  "🟡 Payment မပြုလုပ်ရသေးပါ",
    "WAITING_APPROVAL": "🟠 Payment စစ်ဆေးနေပါသည်",
    "APPROVED":         "🟢 Payment အတည်ပြုပြီး",
    "REJECTED":         "🔴 Payment ပယ်ဖျက်ထားပါသည်",
    "CANCELLED":        "⚪ Order Cancelled",
}

# ──────────────────────────────────────────────
# Orders List
# ──────────────────────────────────────────────
NO_ORDERS_FOUND = (
    "📋 <b>Orders မရှိသေးပါ</b>\n\n"
    "ဝယ်ယူရန် အောက်မှ ခလုတ်ကို နှိပ်ပါ။"
)


def orders_list(orders: list[dict]) -> str:
    lines = ["📋 <b>သင်၏ Orders</b>\n"]
    for i, order in enumerate(orders, 1):
        status = STATUS_LABELS.get(order.get("status", ""), order.get("status", ""))
        amount = f"{order.get('totalAmount', 0):,}"
        code = order.get("orderCode", "—")
        lines.append(f"{i}. <code>{code}</code>")
        lines.append(f"   {status}")
        lines.append(f"   💰 {amount} MMK\n")
    return "\n".join(lines)

# ──────────────────────────────────────────────
# Order Approved Notification (req #27)
# ──────────────────────────────────────────────
def order_approved(order_code: str, amount: int, movies: list[dict]) -> str:
    amount_formatted = f"{amount:,}"
    movie_lines = "\n".join(
        f"🎬 <b>{m['title']}</b>\n🔗 <a href=\"{m['watchLink']}\">Watch Now</a>"
        for m in movies
    )
    return (
        f"🎉 <b>Order Approved!</b>\n\n"
        f"Order ID:\n<code>{order_code}</code>\n\n"
        f"Payment: <b>{amount_formatted} MMK</b>\n\n"
        f"ဝယ်ယူထားသော VIP Content များ:\n\n"
        f"{movie_lines}"
    )

# ──────────────────────────────────────────────
# Order Rejected Notification (req #28)
# ──────────────────────────────────────────────
def order_rejected(order_code: str, reason: str | None) -> str:
    reason_text = reason or "—"
    return (
        f"❌ <b>Payment မအောင်မြင်ပါ</b>\n\n"
        f"Order ID:\n<code>{order_code}</code>\n\n"
        f"အကြောင်းရင်း:\n{reason_text}\n\n"
        f"Order အသစ်ပြုလုပ်ပြီး ပြန်လည်ကြိုးစားနိုင်ပါတယ်။"
    )

# ──────────────────────────────────────────────
# Cancel / Error
# ──────────────────────────────────────────────
ORDER_CANCELLED = "✅ Order ပယ်ဖျက်ပြီးပါပြီ။"
SESSION_EXPIRED = (
    "⏳ <b>Session သက်တမ်းကုန်သွားပါပြီ</b>\n\n"
    "Order အသစ်ပြန်စနိုင်ပါတယ်။"
)
RATE_LIMITED = "⏳ ခဏလောက်စောင့်ပြီး ပြန်လည်ကြိုးစားပေးပါ။"
NO_MOVIES_AVAILABLE = (
    "😔 လောလောဆယ် ရနိုင်သော ဇာတ်ကားများ မရှိသေးပါ။\n"
    "နောက်မှ ပြန်ကြည့်ပေးပါ။"
)
UNEXPECTED_MESSAGE = (
    "ℹ️ ဆက်လက်လုပ်ဆောင်ရန် အောက်မှ ခလုတ်ကို နှိပ်ပါ။"
)
ERROR_GENERIC = (
    "❌ တစ်ခုခု မှားယွင်းနေပါသည်။ ခဏကြာပြီး ထပ်စမ်းကြည့်ပေးပါ။"
)
