"""
main.py

DramaZone VIP Bot — FastAPI application entry point.

Security layers implemented:
  HTTP layer  — Rate limiting (IP sliding window), security headers,
                request-size cap, webhook secret validation
  Bot layer   — Per-user anti-flood protection (see app/utils/anti_flood.py)
  DB layer    — Atomic status transitions (approve/reject)
  Auth layer  — Admin-only handlers, Telegram ID allowlist
"""
from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from starlette.middleware.trustedhost import TrustedHostMiddleware
from telegram import Update

from app.config import settings
from app.database.mongodb import connect as db_connect, close as db_close
from app.database.indexes import ensure_indexes
from app.middleware.rate_limiter import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("dramazone")

# ── Constants ─────────────────────────────────────────────────────────────────
# Maximum allowed request body size (bytes).  Telegram updates are small JSON;
# screenshots are never sent to our webhook (only file_ids are).
# 512 KB is more than enough for any legitimate Telegram update.
MAX_REQUEST_BODY_BYTES = 512 * 1024   # 512 KB


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

    # Schedule anti-flood cleanup every 5 minutes via bot job_queue
    if settings.customer_bot_token:
        from app.bots.customer_bot import get_customer_app
        from app.utils.anti_flood import cleanup_stale_windows

        async def _flood_cleanup(ctx):
            removed = cleanup_stale_windows(older_than=300)
            if removed:
                logger.debug("Anti-flood cleanup: removed %d stale entries.", removed)

        capp = get_customer_app()
        if capp.job_queue:
            capp.job_queue.run_repeating(_flood_cleanup, interval=300, first=300)

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
    # Never expose docs in production — set DOCS_ENABLED=true only locally
    docs_url="/docs" if os.getenv("DOCS_ENABLED", "false").lower() == "true" else None,
    redoc_url=None,
    lifespan=lifespan,
)

# ── Security Middleware (order matters — outermost runs first) ─────────────────
#
# Stack (request flow):
#   Client → RateLimitMiddleware → SecurityHeadersMiddleware → Routes
#
# RateLimitMiddleware must be outermost so blocked requests never reach routes.
# SecurityHeadersMiddleware wraps all responses (including rate-limit 429s).

app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


# ── Request body size guard ───────────────────────────────────────────────────
@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    """
    Reject oversized request bodies before they are read into memory.

    This prevents memory-exhaustion attacks via huge POST bodies.
    Telegram webhook payloads are always small JSON; 512 KB is generous.
    """
    content_length = request.headers.get("Content-Length")
    if content_length:
        try:
            if int(content_length) > MAX_REQUEST_BODY_BYTES:
                logger.warning(
                    "SECURITY: Oversized request (%s bytes) from %s rejected.",
                    content_length,
                    request.client.host if request.client else "unknown",
                )
                return HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Request body too large.",
                )
        except ValueError:
            pass
    return await call_next(request)


# ── Webhook secret validation ─────────────────────────────────────────────────
def _validate_webhook_secret(request: Request, expected_secret: str) -> None:
    """
    Validate X-Telegram-Bot-Api-Secret-Token header.

    Raises HTTP 403 on mismatch — never reveals the expected secret.
    Timing-safe comparison prevents timing-oracle attacks.
    """
    if not expected_secret:
        return  # Secret not configured — dev/polling mode only

    import hmac
    received = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    # hmac.compare_digest is constant-time regardless of string length
    if not hmac.compare_digest(received, expected_secret):
        logger.warning(
            "SECURITY: Webhook secret mismatch on %s from %s",
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
        data   = await request.json()
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
        data   = await request.json()
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
        # Limit the number of concurrent connections (DDoS protection)
        limit_concurrency=100,
        limit_max_requests=10_000,
        # Timeout for slow clients (slow-loris attack mitigation)
        timeout_keep_alive=5,
    )
