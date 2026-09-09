"""
app/api/webhook.py
────────────────────────────────────────────────────────────────────────
FastAPI Webhook Router for Telegram Bot Updates.

Receives incoming updates from Telegram via HTTP POST in production mode.
Validates X-Telegram-Bot-Api-Secret-Token header.
"""

import logging
from fastapi import APIRouter, Request, Header, HTTPException, status
from telegram import Update

from app.config import config
from app.bot.customer.bot import customer_bot_app
from app.bot.admin.bot import admin_bot_app

logger = logging.getLogger("dramazone.api.webhook")

router = APIRouter(prefix="/api/v1/webhook", tags=["Webhook"])


@router.post("/customer", status_code=status.HTTP_200_OK)
async def customer_bot_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None, alias="X-Telegram-Bot-Api-Secret-Token")
):
    """
    Handle incoming updates from Telegram for Customer Bot.
    """
    if config.webhook_secret and x_telegram_bot_api_secret_token != config.webhook_secret:
        logger.warning("Invalid webhook secret token received on Customer webhook.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Telegram webhook secret token"
        )

    if not customer_bot_app:
        logger.error("Customer bot app is not initialized.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Customer bot application unavailable"
        )

    try:
        data = await request.json()
        update = Update.de_json(data, customer_bot_app.bot)
        await customer_bot_app.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error processing Customer Telegram update: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.post("/admin", status_code=status.HTTP_200_OK)
async def admin_bot_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None, alias="X-Telegram-Bot-Api-Secret-Token")
):
    """
    Handle incoming updates from Telegram for Admin Bot.
    """
    if config.webhook_secret and x_telegram_bot_api_secret_token != config.webhook_secret:
        logger.warning("Invalid webhook secret token received on Admin webhook.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Telegram webhook secret token"
        )

    if not admin_bot_app:
        logger.error("Admin bot app is not initialized.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin bot application unavailable"
        )

    try:
        data = await request.json()
        update = Update.de_json(data, admin_bot_app.bot)
        await admin_bot_app.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error processing Admin Telegram update: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}
