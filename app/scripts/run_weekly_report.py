"""CLI: Генерация недельного сводного отчёта ProcessFix AI.

Запуск:
    python -m app.scripts.run_weekly_report
    python -m app.scripts.run_weekly_report --week-start 2026-02-16
    python -m app.scripts.run_weekly_report --chat-id 123456789

Airflow вызывает каждый понедельник через weekly_report_pipeline DAG.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timedelta

from app.core.config import get_settings
from app.core.database import get_ch_client
from app.services.excel import build_excel_report
from app.services.analytics import DailyReport, AnomalyRecord
from app.services.llm import generate_five_whys
from app.services.telegram import send_report

import pandas as pd

logger = logging.getLogger("processfix.cli.weekly_report")


def _load_weekly_losses(week_start: datetime, week_end: datetime) -> pd.DataFrame:
    """Загрузить агрегированные потери за неделю из mart_daily_losses."""
    settings = get_settings()
    client = get_ch_client()

    if settings.analytics_source == "marts":
        query = """
            SELECT
                operation_name,
                any(role_name)          AS role_name,
                sum(event_count)        AS event_count,
                avg(avg_duration_sec)   AS avg_duration_sec,
                any(norm_seconds)       AS norm_seconds,
                any(hourly_rate_rub)    AS hourly_rate_rub,
                avg(delta_sec)          AS delta_sec,
                sum(total_loss_rub)     AS total_loss_rub
            FROM mart_daily_losses FINAL
            WHERE event_date >= %(start)s AND event_date < %(end)s
            GROUP BY operation_name
            ORDER BY total_loss_rub DESC
        """
    else:
        query = """
            SELECT
                el.operation_name,
                '' AS role_name,
                count()                  AS event_count,
                avg(el.duration_seconds) AS avg_duration_sec,
                0                        AS norm_seconds,
                0                        AS hourly_rate_rub,
                0                        AS delta_sec,
                0                        AS total_loss_rub
            FROM event_logs el
            WHERE el.start_time >= %(start)s AND el.start_time < %(end)s
            GROUP BY el.operation_name
            ORDER BY event_count DESC
        """

    result = client.query(query, parameters={
        "start": str(week_start.date()),
        "end": str(week_end.date()),
    })
    cols = [
        "operation_name", "role_name", "event_count", "avg_duration_sec",
        "norm_seconds", "hourly_rate_rub", "delta_sec", "total_loss_rub",
    ]
    df = pd.DataFrame(result.result_rows, columns=cols)
    if not df.empty:
        df["avg_duration_min"] = (df["avg_duration_sec"] / 60).round(2)
        df["norm_min"] = (df["norm_seconds"] / 60).round(2)
    return df


async def _run(week_start: datetime, chat_id: str | None) -> None:
    week_end = week_start + timedelta(days=7)
    logger.info("Недельный отчёт: %s — %s", week_start.date(), week_end.date())

    losses_df = _load_weekly_losses(week_start, week_end)

    if losses_df.empty:
        logger.warning("Нет данных за неделю.")
        return

    total_loss = round(float(losses_df["total_loss_rub"].sum()), 2)
    total_events = int(losses_df["event_count"].sum())

    top = losses_df.head(3)
    anomalies = [
        AnomalyRecord(
            operation_name=row["operation_name"],
            avg_duration_sec=round(float(row["avg_duration_sec"]), 1),
            norm_seconds=int(row["norm_seconds"]),
            delta_sec=round(float(row["delta_sec"]), 1),
            hourly_rate_rub=float(row["hourly_rate_rub"]),
            total_loss_rub=float(row["total_loss_rub"]),
            event_count=int(row["event_count"]),
        )
        for _, row in top.iterrows()
    ]

    report = DailyReport(
        report_date=week_start,
        total_loss_rub=total_loss,
        total_events=total_events,
        losses_df=losses_df,
        top_anomalies=anomalies,
    )

    ai_text = ""
    if anomalies:
        ai_text = await generate_five_whys(anomalies[0])

    file_bytes = build_excel_report(report, ai_text)
    filename = f"processfix_week_{week_start:%Y-%m-%d}.xlsx"
    logger.info("Excel (weekly): %s (%.1f KB)", filename, len(file_bytes) / 1024)

    ok = await send_report(
        file_bytes=file_bytes,
        total_loss_rub=total_loss,
        chat_id=chat_id,
        filename=filename,
    )
    if ok:
        logger.info("Недельный отчёт отправлен в Telegram.")
    else:
        logger.warning("Telegram-отправка пропущена.")


def main() -> None:
    parser = argparse.ArgumentParser(description="ProcessFix AI — Weekly Report CLI")
    parser.add_argument(
        "--week-start",
        type=str,
        default=None,
        help="Понедельник начала недели (YYYY-MM-DD). По умолчанию: прошлый понедельник.",
    )
    parser.add_argument(
        "--chat-id",
        type=str,
        default=None,
        help="Telegram chat_id",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    if args.week_start:
        try:
            week_start = datetime.strptime(args.week_start, "%Y-%m-%d")
        except ValueError:
            logger.error("Неверный формат: %s", args.week_start)
            sys.exit(1)
    else:
        today = datetime.utcnow()
        week_start = today - timedelta(days=today.weekday() + 7)
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    asyncio.run(_run(week_start, args.chat_id))


if __name__ == "__main__":
    main()
