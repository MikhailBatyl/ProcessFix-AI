"""Доставка отчётов через Telegram Bot (aiogram 3.x)."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import BufferedInputFile

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def send_report(
    file_bytes: bytes,
    total_loss_rub: float,
    *,
    chat_id: str | None = None,
    filename: str = "processfix_report.xlsx",
) -> bool:
    """Отправить .xlsx отчёт в Telegram-чат с кратким summary в caption.

    Returns ``True`` при успешной отправке, ``False`` при ошибке.
    """
    settings = get_settings()
    chat_id = chat_id or settings.telegram_chat_id

    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN не задан — отправка пропущена.")
        return False
    if not chat_id:
        logger.warning("TELEGRAM_CHAT_ID не задан — отправка пропущена.")
        return False

    caption = (
        f"📊 ProcessFix AI — Ежедневный отчёт\n"
        f"💰 Суммарные потери ФОТ: {total_loss_rub:,.2f} ₽\n"
        f"Подробности в файле ↓"
    )

    bot = Bot(token=settings.telegram_bot_token)
    try:
        document = BufferedInputFile(file=file_bytes, filename=filename)
        await bot.send_document(chat_id=int(chat_id), document=document, caption=caption)
        logger.info("Отчёт отправлен в Telegram (chat_id=%s)", chat_id)
        return True
    except Exception:
        logger.exception("Ошибка отправки в Telegram")
        return False
    finally:
        await bot.session.close()
