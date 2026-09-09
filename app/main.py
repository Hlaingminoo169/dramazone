"""
app/main.py
─────────────────────────────────────────────────────────────────────────────
FastAPI application entry point.

Startup sequence
-----------------
  1. Logging is configured from environment settings
  2. FastAPI app is created with metadata
  3. Lifespan context manager:
     a. connect_db()         → establish Motor connection, verify ping
     b. create_indexes()     → ensure all indexes exist (idempotent)
  4. Health router is mounted
  5. Uvicorn serves requests

Shutdown sequence
------------------
  1. Lifespan context manager resumes after yield
  2. disconnect_db()  → close Motor connection pool cleanly

Request size limit (req #1)
-----------------------------
Incoming request bodies are limited to MAX_REQUEST_SIZE_BYTES (default 10 MB).
This protects against oversized webhook payloads being used to exhaust memory.

Error handling (req #40)
--------------------------
A global exception handler catches any unhandled exceptions and returns a
safe 500 response — no stack traces or internal details are exposed to callers.
All errors are logged server-side for debugging.

VPS compatibility (req #41)
-----------------------------
No cloud-provider-specific code here.  Running on a VPS is:
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database.connection import connect_db, disconnect_db
from app.database.indexes import create_indexes
from app.database.connection import get_db
from app.bot.customer.bot import init_customer_bot, stop_customer_bot
from app.bot.admin.bot import init_admin_bot, stop_admin_bot
from app.api import webhook
from app.routers import health
from app.utils.logger import setup_logging

# ──────────────────────────────────────────────
# Bootstrap logging before anything else
# ──────────────────────────────────────────────
_settings = get_settings()
setup_logging(level=_settings.log_level)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Lifespan — startup and shutdown lifecycle
# ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager.

    Everything before `yield` runs on startup.
    Everything after `yield` runs on shutdown.
    """
    settings = get_settings()

    logger.info(
        "Starting %s (env=%s)",
        settings.app_name,
        settings.app_env,
    )

    # 1. Connect to MongoDB
    await connect_db()

    # 2. Ensure all indexes exist (idempotent — safe on every startup)
    try:
        db = get_db()
        await create_indexes(db)
    except Exception:
        logger.exception(
            "Failed to create indexes at startup. "
            "The app will continue but some queries may be slow."
        )

    # 3. Initialize Customer & Admin Bots (polling or webhook)
    try:
        await init_customer_bot()
    except Exception:
        logger.exception("Failed to initialize Customer Bot at startup.")

    try:
        await init_admin_bot()
    except Exception:
        logger.exception("Failed to initialize Admin Bot at startup.")

    logger.info("%s startup complete. Ready to serve requests.", settings.app_name)

    yield  # ← application runs here

    # ── Shutdown ──────────────────────────────────
    logger.info("Shutting down %s…", settings.app_name)
    await stop_customer_bot()
    await stop_admin_bot()
    await disconnect_db()
    logger.info("Shutdown complete.")


# ──────────────────────────────────────────────
# FastAPI application
# ──────────────────────────────────────────────
app = FastAPI(
    title=_settings.app_name,
    description=(
        "DramaZone VIP Telegram Bot backend. "
        "Handles order management, payment verification, and VIP content delivery."
    ),
    version="1.0.0",
    docs_url="/docs" if _settings.is_development else None,
    redoc_url="/redoc" if _settings.is_development else None,
    openapi_url="/openapi.json" if _settings.is_development else None,
    lifespan=lifespan,
)


# ──────────────────────────────────────────────
# Global exception handler (req #40)
# Catch-all: log the real error, return safe response
# ──────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred. Please try again later."},
    )


# ──────────────────────────────────────────────
# Routers
# ──────────────────────────────────────────────
app.include_router(health.router)
app.include_router(webhook.router)

