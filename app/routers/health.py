"""
app/routers/health.py
─────────────────────────────────────────────────────────────────────────────
Health check endpoints.

Endpoints
---------
  GET /health     → Basic liveness check (always 200 if process is running)
  GET /health/db  → MongoDB connectivity check (200 ok / 503 degraded)

Why two separate endpoints?
-----------------------------
- `/health`     → Used by process managers (systemd, Docker, Railway) to
                  know if the process is alive.  Should always return 200.
- `/health/db`  → Used during deployment validation and by monitoring tools
                  to confirm end-to-end database connectivity.  Returns 503
                  if MongoDB is unreachable, which is useful for load
                  balancer health checks.

Security note (req #40)
-------------------------
The `/health/db` endpoint returns a simple status string on error — it
does NOT expose the MongoDB URI, error messages, or any infrastructure
details to callers.  Detailed errors are logged server-side only.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database.connection import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Health"])


# ──────────────────────────────────────────────
# GET /health
# ──────────────────────────────────────────────
@router.get(
    "/health",
    summary="Liveness check",
    description=(
        "Returns 200 as long as the process is running. "
        "Does NOT verify database connectivity."
    ),
    response_description="Service is alive",
)
async def health_liveness() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "env": settings.app_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ──────────────────────────────────────────────
# GET /health/db
# ──────────────────────────────────────────────
@router.get(
    "/health/db",
    summary="Database connectivity check",
    description=(
        "Pings MongoDB and returns 200 if connected, 503 if unreachable. "
        "Safe for use as a load-balancer health check."
    ),
    response_description="Database connectivity status",
)
async def health_database() -> JSONResponse:
    t_start = time.monotonic()

    try:
        db = get_db()
        await db.command("ping")
        ping_ms = round((time.monotonic() - t_start) * 1000)

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "ok",
                "database": "connected",
                "ping_ms": ping_ms,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    except RuntimeError:
        # get_db() raises RuntimeError if called before connect_db()
        logger.error("Health check: database client not initialised")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "degraded",
                "database": "not_initialised",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    except Exception:
        # Catch-all: log the real error server-side, return safe response
        # Do NOT expose connection strings or error details to callers (req #40)
        ping_ms = round((time.monotonic() - t_start) * 1000)
        logger.exception("Health check: MongoDB ping failed (ping_ms=%d)", ping_ms)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "degraded",
                "database": "unreachable",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
