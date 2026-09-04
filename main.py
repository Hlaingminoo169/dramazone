"""
main.py
========
FastAPI application entrypoint.
Registers two webhook endpoints — one per bot.
Validates Telegram webhook secret tokens.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database.indexes import create_indexes
from app.database.mongodb import get_db, ping_db, close_client
from app.database.seed import run_seed

# Configure logging early
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("Starting DramaZone VIP Bot System...")

    # 1. Validate config (raises on missing required vars)
    settings = get_settings()
    logger.info("Configuration loaded. Admin IDs: %s", settings.admin_telegram_ids)

    # 2. Verify MongoDB connection
    if not ping_db():
        logger.critical("Cannot connect to MongoDB! Aborting startup.")
        raise RuntimeError("MongoDB connection failed.")

    # 3. Create indexes
    db = get_db()
    create_indexes(db)

    # 4. Seed initial data
    run_seed(db)

    # 5. Initialize bot applications (validates tokens)
    from app.bots.customer_bot import build_customer_app
    from app.bots.admin_bot import build_admin_app

    customer_app = build_customer_app()
    admin_app = build_admin_app()

    await customer_app.initialize()
    await admin_app.initialize()

    logger.info("✅ Both bots initialized successfully.")

    # 6. Register webhooks if BASE_WEBHOOK_URL is configured
    if settings.base_webhook_url:
        customer_webhook_url = f"{settings.base_webhook_url}/webhook/customer"
        admin_webhook_url = f"{settings.base_webhook_url}/webhook/admin"

        await customer_app.bot.set_webhook(
            url=customer_webhook_url,
            secret_token=settings.customer_webhook_secret or None,
            allowed_updates=["message", "callback_query"],
        )
        logger.info("Customer Bot webhook set: %s", customer_webhook_url)

        await admin_app.bot.set_webhook(
            url=admin_webhook_url,
            secret_token=settings.admin_webhook_secret or None,
            allowed_updates=["message", "callback_query"],
        )
        logger.info("Admin Bot webhook set: %s", admin_webhook_url)
    else:
        logger.warning("BASE_WEBHOOK_URL not set — skipping webhook registration.")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await customer_app.shutdown()
    await admin_app.shutdown()
    close_client()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="DramaZone VIP Bot System",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,   # Disable Swagger UI in production
    redoc_url=None,
)


def _verify_secret(request_secret: str | None, configured_secret: str) -> bool:
    """Constant-time comparison of webhook secret tokens."""
    if not configured_secret:
        return True  # Secret not configured — skip validation
    if not request_secret:
        return False
    return hmac.compare_digest(request_secret, configured_secret)


@app.get("/")
async def health_check():
    """Health check endpoint for hosting providers."""
    return {"status": "ok", "service": "DramaZone VIP Bot System"}


@app.get("/health")
async def health():
    """Detailed health check."""
    db_ok = ping_db()
    return {
        "status": "ok" if db_ok else "degraded",
        "mongodb": "connected" if db_ok else "disconnected",
    }


@app.post("/webhook/customer")
async def customer_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    """Receive updates for the Customer Bot."""
    settings = get_settings()

    if not _verify_secret(x_telegram_bot_api_secret_token, settings.customer_webhook_secret):
        logger.warning("Invalid secret token on /webhook/customer")
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    from app.bots.customer_bot import process_customer_update
    await process_customer_update(data)

    return JSONResponse({"ok": True})


@app.post("/webhook/admin")
async def admin_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    """Receive updates for the Admin Bot."""
    settings = get_settings()

    if not _verify_secret(x_telegram_bot_api_secret_token, settings.admin_webhook_secret):
        logger.warning("Invalid secret token on /webhook/admin")
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    from app.bots.admin_bot import process_admin_update
    await process_admin_update(data)

    return JSONResponse({"ok": True})
