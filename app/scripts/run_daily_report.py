"""CLI: Генерация и отправка ежедневного отчёта ProcessFix AI.

Запуск:
    python -m app.scripts.run_daily_report
    python -m app.scripts.run_daily_report --date 2026-02-25
    python -m app.scripts.run_daily_report --date 2026-02-25 --chat-id 123456789

Airflow вызывает этот скрипт через BashOperator / PythonOperator.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime

from app.core.config import get_settings
from app.services.analytics import build_daily_report
from app.services.excel import build_excel_report
from app.services.llm import generate_five_whys
from app.services.telegram import send_report

logger = logging.getLogger("processfix.cli.daily_report")


async def _run(report_date: datetime, chat_id: str | None) -> None:
    settings = get_settings()
    logger.info(
        "Запуск ежедневного отчёта [source=%s, date=%s]",
        settings.analytics_source,
        report_date.date(),
    )

    report = await build_daily_report(report_date=report_date)
    logger.info("Потери: %.2f ₽, событий: %d", report.total_loss_rub, report.total_events)

    ai_text = ""
    if report.top_anomalies:
        ai_text = await generate_five_whys(report.top_anomalies[0])
        logger.info("AI-гипотезы получены для «%s»", report.top_anomalies[0].operation_name)

    file_bytes = build_excel_report(report, ai_text)
    filename = f"processfix_{report_date:%Y-%m-%d}.xlsx"
    logger.info("Excel готов: %s (%.1f KB)", filename, len(file_bytes) / 1024)

    ok = await send_report(
        file_bytes=file_bytes,
        total_loss_rub=report.total_loss_rub,
        chat_id=chat_id,
        filename=filename,
    )
    if ok:
        logger.info("Отчёт отправлен в Telegram.")
    else:
        logger.warning("Telegram-отправка пропущена или не удалась.")


def main() -> None:
    parser = argparse.ArgumentParser(description="ProcessFix AI — Daily Report CLI")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Дата отчёта в формате YYYY-MM-DD (по умолчанию: сегодня)",
    )
    parser.add_argument(
        "--chat-id",
        type=str,
        default=None,
        help="Telegram chat_id (по умолчанию: из TELEGRAM_CHAT_ID)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    if args.date:
        try:
            report_date = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            logger.error("Неверный формат даты: %s (ожидается YYYY-MM-DD)", args.date)
            sys.exit(1)
    else:
        report_date = datetime.utcnow()

    asyncio.run(_run(report_date, args.chat_id))


if __name__ == "__main__":
    main()
