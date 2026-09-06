"""
app/bots/customer_bot.py

Customer bot initialisation — all handlers registered here.
"""
from __future__ import annotations

import logging
from typing import Optional

from telegram.ext import Application, ApplicationBuilder

from app.config import settings

logger = logging.getLogger(__name__)

_customer_app: Optional[Application] = None


def get_customer_app() -> Application:
    """Return the (lazily initialised) customer bot Application."""
    global _customer_app
    if _customer_app is None:
        _customer_app = _build_customer_app()
    return _customer_app


def _build_customer_app() -> Application:
    """Build and configure the customer bot Application with all handlers."""
    if not settings.customer_bot_token:
        raise RuntimeError(
            "CUSTOMER_BOT_TOKEN is not set. "
            "Add it to your .env or hosting environment variables."
        )

    app = (
        ApplicationBuilder()
        .token(settings.customer_bot_token)
        .updater(None)  # Webhook mode — no polling updater
        .build()
    )

    # ── Register handlers in priority order ───────────────────────────────────
    from app.handlers.customer.start import register as reg_start
    from app.handlers.customer.package import register as reg_package
    from app.handlers.customer.movies import register as reg_movies
    from app.handlers.customer.payment import register as reg_payment
    from app.handlers.customer.orders import register as reg_orders

    reg_start(app)
    reg_package(app)
    reg_movies(app)
    reg_payment(app)
    reg_orders(app)

    logger.info("Customer bot application built with all handlers.")
    return app
