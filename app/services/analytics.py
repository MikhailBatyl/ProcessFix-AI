"""Расчёт потерь ФОТ, поиск аномалий, агрегация за последние 24 ч.

Два режима источника данных (``ANALYTICS_SOURCE``):
  * ``raw``   — MVP: агрегируем event_logs из CH, нормативы из PG, джойним в pandas.
  * ``marts`` — Platform: читаем готовую витрину ``mart_daily_losses`` из CH (dbt).

Публичный интерфейс (``build_daily_report``) одинаков в обоих режимах.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import async_session_factory, get_ch_client
from app.db.models import ProcessNorm, TariffFOT

logger = logging.getLogger(__name__)


# ── Публичные dataclass'ы ───────────────────────────────

@dataclass
class AnomalyRecord:
    """Одна строка в таблице аномалий."""

    operation_name: str
    avg_duration_sec: float
    norm_seconds: int
    delta_sec: float
    hourly_rate_rub: float
    total_loss_rub: float
    event_count: int


@dataclass
class DailyReport:
    """Результат полного аналитического расчёта за сутки."""

    report_date: datetime
    total_loss_rub: float
    total_events: int
    losses_df: pd.DataFrame
    top_anomalies: list[AnomalyRecord]


# ── Raw-режим (MVP) ────────────────────────────────────

async def _load_norms_from_pg() -> pd.DataFrame:
    """Загрузить нормативы + ставки из PostgreSQL в DataFrame."""
    async with async_session_factory() as session:
        session: AsyncSession
        stmt = select(
            ProcessNorm.operation_name,
            ProcessNorm.norm_seconds,
            TariffFOT.hourly_rate_rub,
            TariffFOT.role_name,
        ).join(TariffFOT, ProcessNorm.role_id == TariffFOT.id)

        rows = (await session.execute(stmt)).all()

    return pd.DataFrame(rows, columns=["operation_name", "norm_seconds", "hourly_rate_rub", "role_name"])


def _load_events_raw(since: datetime) -> pd.DataFrame:
    """Агрегировать event_logs за период из ClickHouse (raw-таблица)."""
    client = get_ch_client()

    query = """
        SELECT
            operation_name,
            count()                       AS event_count,
            avg(duration_seconds)         AS avg_duration_sec,
            sum(duration_seconds)         AS total_duration_sec
        FROM event_logs
        WHERE start_time >= %(since)s
        GROUP BY operation_name
    """
    result = client.query(query, parameters={"since": since})
    cols = ["operation_name", "event_count", "avg_duration_sec", "total_duration_sec"]
    return pd.DataFrame(result.result_rows, columns=cols)


def _calculate_losses(events_df: pd.DataFrame, norms_df: pd.DataFrame) -> pd.DataFrame:
    """Джойн событий с нормативами и расчёт потерь ФОТ.

    Формула:
        delta = avg_duration_sec - norm_seconds
        if delta > 0:
            loss_per_event = (delta / 3600) * hourly_rate_rub
            total_loss    = loss_per_event * event_count
    """
    merged = events_df.merge(norms_df, on="operation_name", how="inner")

    merged["delta_sec"] = merged["avg_duration_sec"] - merged["norm_seconds"]
    merged["delta_sec"] = merged["delta_sec"].clip(lower=0)

    merged["loss_per_event_rub"] = (merged["delta_sec"] / 3600) * merged["hourly_rate_rub"]
    merged["total_loss_rub"] = merged["loss_per_event_rub"] * merged["event_count"]

    merged["avg_duration_min"] = (merged["avg_duration_sec"] / 60).round(2)
    merged["norm_min"] = (merged["norm_seconds"] / 60).round(2)
    merged["total_loss_rub"] = merged["total_loss_rub"].round(2)

    return merged.sort_values("total_loss_rub", ascending=False).reset_index(drop=True)


async def _build_losses_raw(report_date: datetime) -> pd.DataFrame:
    """Полный расчёт потерь из raw-источников (MVP-путь)."""
    since = report_date - timedelta(hours=24)
    norms_df = await _load_norms_from_pg()
    events_df = _load_events_raw(since)
    if events_df.empty:
        return pd.DataFrame()
    return _calculate_losses(events_df, norms_df)


# ── Marts-режим (dbt-витрина) ──────────────────────────

def _build_losses_marts(report_date: datetime) -> pd.DataFrame:
    """Чтение готовой витрины mart_daily_losses из ClickHouse."""
    client = get_ch_client()
    target_date = report_date.date()

    query = """
        SELECT
            operation_name,
            role_name,
            event_count,
            avg_duration_sec,
            norm_seconds,
            hourly_rate_rub,
            delta_sec,
            total_loss_rub
        FROM mart_daily_losses FINAL
        WHERE event_date = %(target_date)s
        ORDER BY total_loss_rub DESC
    """
    result = client.query(query, parameters={"target_date": str(target_date)})
    cols = [
        "operation_name", "role_name", "event_count", "avg_duration_sec",
        "norm_seconds", "hourly_rate_rub", "delta_sec", "total_loss_rub",
    ]
    df = pd.DataFrame(result.result_rows, columns=cols)

    if not df.empty:
        df["avg_duration_min"] = (df["avg_duration_sec"] / 60).round(2)
        df["norm_min"] = (df["norm_seconds"] / 60).round(2)

    return df


# ── Публичный интерфейс ────────────────────────────────

def _df_to_anomalies(df: pd.DataFrame, top_n: int) -> list[AnomalyRecord]:
    top = df.head(top_n)
    return [
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


async def build_daily_report(
    top_n: int = 3,
    report_date: datetime | None = None,
) -> DailyReport:
    """Основная точка входа: собрать полный аналитический отчёт.

    Источник данных определяется настройкой ``ANALYTICS_SOURCE``.
    """
    settings = get_settings()
    report_date = report_date or datetime.utcnow()

    if settings.analytics_source == "marts":
        logger.info("Источник: mart_daily_losses (dbt-витрина)")
        losses_df = _build_losses_marts(report_date)
    else:
        logger.info("Источник: raw event_logs + PG norms")
        losses_df = await _build_losses_raw(report_date)

    if losses_df.empty:
        logger.warning("Нет данных для отчёта за %s.", report_date)
        return DailyReport(
            report_date=report_date,
            total_loss_rub=0.0,
            total_events=0,
            losses_df=pd.DataFrame(),
            top_anomalies=[],
        )

    total_loss = round(float(losses_df["total_loss_rub"].sum()), 2)
    total_events = int(losses_df["event_count"].sum())
    anomalies = _df_to_anomalies(losses_df, top_n)

    logger.info(
        "Отчёт [%s]: %d событий, потери %.2f ₽, аномалий: %d",
        settings.analytics_source,
        total_events,
        total_loss,
        len(anomalies),
    )

    return DailyReport(
        report_date=report_date,
        total_loss_rub=total_loss,
        total_events=total_events,
        losses_df=losses_df,
        top_anomalies=anomalies,
    )
