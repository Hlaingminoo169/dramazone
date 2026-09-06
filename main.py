"""
main.py

DramaZone VIP Bot — FastAPI application entry point.

Steps implemented:
  1  — MongoDB connection + indexes
  2  — Project structure
  3  — GET / and GET /health
  4  — POST /webhook/customer and /webhook/admin (with secret validation)
  5  — Database schema (via indexes + services)
  6  — Customer /start
  7  — Package selection
  8  — Myanmar number input
  9  — Movie selection
  10 — Payment method
  11 — Order creation + screenshot
  12 — Admin bot
  13 — Admin payment notification
  14 — Approve order
  15 — Reject order + reason
  16 — Order history
  17 — Contact admin
  18 — Security (webhook secrets, admin auth, atomic ops)
"""
from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from telegram import Update

from app.config import settings
from app.database.mongodb import connect as db_connect, close as db_close
from app.database.indexes import ensure_indexes

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("dramazone")


# ── Application lifespan ─────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("DramaZone VIP starting up…")

    # MongoDB
    try:
        db_connect()
        ensure_indexes()
    except RuntimeError as exc:
        logger.critical("Startup failed: %s", exc)
        raise

    # Seed initial movie data (idempotent)
    from app.services.movie_service import seed_movies
    seed_movies()

    # Initialise bot Applications (validates tokens eagerly)
    if settings.customer_bot_token:
        from app.bots.customer_bot import get_customer_app
        customer_app = get_customer_app()
        await customer_app.initialize()

    if settings.admin_bot_token:
        from app.bots.admin_bot import get_admin_app
        admin_app = get_admin_app()
        await admin_app.initialize()

    logger.info("DramaZone VIP is ready.")

    yield  # ← application running

    # Shutdown
    logger.info("DramaZone VIP shutting down…")
    db_close()
    logger.info("Goodbye.")


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="DramaZone VIP Bot API",
    description="Telegram VIP content purchasing system",
    version="0.1.0",
    docs_url="/docs" if os.getenv("DOCS_ENABLED", "false").lower() == "true" else None,
    redoc_url=None,
    lifespan=lifespan,
)


# ── Webhook secret validation ─────────────────────────────────────────────────
def _validate_webhook_secret(request: Request, expected_secret: str) -> None:
    """
    Validate X-Telegram-Bot-Api-Secret-Token header.
    Raises HTTP 403 on mismatch — never reveals the expected secret.
    """
    if not expected_secret:
        return  # Secret not configured — dev mode only

    received = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if received != expected_secret:
        logger.warning(
            "Webhook secret mismatch on %s from %s",
            request.url.path,
            request.client.host if request.client else "unknown",
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    return {"service": "DramaZone VIP Bot API", "version": "0.1.0"}


@app.get("/health")
async def health():
    """Lightweight health check — suitable for hosting platform probes."""
    return {"status": "ok"}


@app.post("/webhook/customer", include_in_schema=False)
async def customer_webhook(request: Request):
    """Receive and process Customer Bot Telegram updates."""
    _validate_webhook_secret(request, settings.customer_webhook_secret)

    try:
        from app.bots.customer_bot import get_customer_app
        data = await request.json()
        update = Update.de_json(data, get_customer_app().bot)
        await get_customer_app().process_update(update)
    except Exception as exc:
        # Always return 200 — Telegram retries on non-200.
        logger.exception("Error processing customer update: %s", type(exc).__name__)

    return {"ok": True}


@app.post("/webhook/admin", include_in_schema=False)
async def admin_webhook(request: Request):
    """Receive and process Admin Bot Telegram updates."""
    _validate_webhook_secret(request, settings.admin_webhook_secret)

    try:
        from app.bots.admin_bot import get_admin_app
        data = await request.json()
        update = Update.de_json(data, get_admin_app().bot)
        await get_admin_app().process_update(update)
    except Exception as exc:
        logger.exception("Error processing admin update: %s", type(exc).__name__)

    return {"ok": True}


# ── Dev entrypoint ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", settings.port))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )
