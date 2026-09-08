import urllib.request, json, sys

BASE_URL        = "https://dramazone.fastapicloud.dev"
CUSTOMER_TOKEN  = "8882624795:AAHp9wf2_-RVd4D7TDFzzsXRnJRhD1YQjfQ"
ADMIN_TOKEN     = "8856782721:AAFweh9P6mTsEArGKX9QYUJg9dTveV4nMok"
CUSTOMER_SECRET = "6F4UWBZuA09n0j2BShf1wZcRqvDwtFMjFueVsiOQwYU"
ADMIN_SECRET    = "kRdjOwGgu4RCABslNiEZluAWF6TPtehpwnebgFjjBDc"


def set_webhook(token, webhook_url, secret):
    api_url = "https://api.telegram.org/bot{}/setWebhook".format(token)
    payload = json.dumps({
        "url": webhook_url,
        "secret_token": secret,
        "allowed_updates": ["message", "callback_query"],
        "drop_pending_updates": True,
    }).encode()
    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def get_webhook_info(token):
    api_url = "https://api.telegram.org/bot{}/getWebhookInfo".format(token)
    with urllib.request.urlopen(api_url, timeout=10) as resp:
        return json.loads(resp.read())


# --- Set webhooks ---
print("=== Setting Customer Bot Webhook ===")
r = set_webhook(CUSTOMER_TOKEN, BASE_URL + "/webhook/customer", CUSTOMER_SECRET)
print("  ok={} msg={}".format(r["ok"], r.get("description", "")))

print("=== Setting Admin Bot Webhook ===")
r = set_webhook(ADMIN_TOKEN, BASE_URL + "/webhook/admin", ADMIN_SECRET)
print("  ok={} msg={}".format(r["ok"], r.get("description", "")))

# --- Verify ---
print()
print("=== Customer Bot Webhook Info ===")
info = get_webhook_info(CUSTOMER_TOKEN)["result"]
print("  url:", info.get("url"))
print("  pending:", info.get("pending_update_count", 0))
print("  last_error:", info.get("last_error_message", "none"))

print()
print("=== Admin Bot Webhook Info ===")
info = get_webhook_info(ADMIN_TOKEN)["result"]
print("  url:", info.get("url"))
print("  pending:", info.get("pending_update_count", 0))
print("  last_error:", info.get("last_error_message", "none"))
