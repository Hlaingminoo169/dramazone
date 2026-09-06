"""
app/bots/admin_bot.py

Admin bot initialisation — all handlers registered here.
"""
from __future__ import annotations

import logging
from typing import Optional

from telegram.ext import Application, ApplicationBuilder

from app.config import settings

logger = logging.getLogger(__name__)

_admin_app: Optional[Application] = None


def get_admin_app() -> Application:
    """Return the (lazily initialised) admin bot Application."""
    global _admin_app
    if _admin_app is None:
        _admin_app = _build_admin_app()
    return _admin_app


def _build_admin_app() -> Application:
    """Build and configure the admin bot Application with all handlers."""
    if not settings.admin_bot_token:
        raise RuntimeError(
            "ADMIN_BOT_TOKEN is not set. "
            "Add it to your .env or hosting environment variables."
        )

    app = (
        ApplicationBuilder()
        .token(settings.admin_bot_token)
        .updater(None)
        .build()
    )

    # ── Register handlers ─────────────────────────────────────────────────────
    from app.handlers.admin.start import register as reg_start
    from app.handlers.admin.orders import register as reg_orders
    from app.handlers.admin.approval import register as reg_approval

    reg_start(app)
    reg_orders(app)
    reg_approval(app)

    logger.info("Admin bot application built with all handlers.")
    return app
