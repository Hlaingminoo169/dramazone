"""
app/bot/admin/messages.py
────────────────────────────────────────────────────────────────────────
Admin Bot Myanmar Messages & Formatting Templates.
"""

ACCESS_DENIED = (
    "⛔ **Access Denied (ခွင့်ပြုချက် မရှိပါ)**\n\n"
    "လူကြီးမင်းသည် DramaZone Admin အဖွဲ့ဝင် မဟုတ်ပါသဖြင့် ဤ Bot ကို အသုံးပြုခွင့် မရှိပါ။"
)

ADMIN_WELCOME = (
    "🛠️ **DramaZone VIP Admin Management Bot**\n\n"
    "မင်္ဂလာပါ Admin! အောက်ပါ Command များနှင့် Button များကို အသုံးပြုနိုင်ပါသည်:\n\n"
    "• /admin — Dashboard & Dynamic Analytics ကြည့်ရန်\n"
    "• /pending — မစစ်ဆေးရသေးသော Pending Order များကို ကြည့်ရန်\n"
    "• /movies — လက်ရှိ active ဖြစ်နေသော ဇာတ်ကားများ ကြည့်ရန်\n"
)

NO_PENDING_ORDERS = (
    "✅ **စစ်ဆေးရန် Pending Order မရှိသေးပါ**\n\n"
    "လက်ရှိတွင် စစ်ဆေးရန် ကျန်ရှိနေသော Order မရှိပါ။"
)

REJECT_REASON_OPTIONS = {
    "invalid_screenshot": "ငွေလွှဲပြေစာ (Screenshot) မမှန်ကန်ပါ / မသဲကွဲပါ",
    "wrong_amount": "လွှဲပြောင်းလိုက်သော ငွေပမာဏ မကိုက်ညီပါ",
    "duplicate": "ငွေလွှဲပြေစာ အဟောင်းဖြစ်နေပါသည် (Duplicate Proof)",
    "other": "အခြား အကြောင်းအရင်း"
}


def format_dashboard(stats: dict) -> str:
    """Format dashboard statistics into readable Markdown."""
    return (
        f"📊 **DramaZone VIP Dashboard & Analytics**\n\n"
        f"👥 **အသုံးပြုသူ အရေအတွက်:** `{stats['total_users']}` ယောက်\n"
        f"📦 **စုစုပေါင်း အော်ဒါ:** `{stats['total_orders']}` ခု\n\n"
        f"⏳ **Pending စစ်ဆေးရန်ကျန်:** `{stats['pending_count']}` ခု\n"
        f"✅ **Approve အတည်ပြုပြီး:** `{stats['approved_count']}` ခု\n"
        f"❌ **Reject ငြင်းပယ်ထား:** `{stats['rejected_count']}` ခု\n\n"
        f"💰 **ယနေ့ ရရှိငွေ (Today Revenue):** `{stats['today_revenue']:,} MMK` ({stats['today_approved_count']} orders)\n"
        f"💵 **စုစုပေါင်း ရရှိငွေ (Total Revenue):** `{stats['total_revenue']:,} MMK`"
    )
