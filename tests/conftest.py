"""Общие фикстуры для unit-тестов ProcessFix AI.

Все тесты работают БЕЗ живых баз данных — PG и CH замокированы.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from app.services.analytics import AnomalyRecord, DailyReport


# ── Фабрики тестовых данных ─────────────────────────────

@pytest.fixture()
def sample_norms_df() -> pd.DataFrame:
    return pd.DataFrame({
        "operation_name": ["Комплектация заказа", "Погрузка паллеты", "Проверка качества"],
        "norm_seconds": [300, 180, 240],
        "hourly_rate_rub": [450.0, 520.0, 480.0],
        "role_name": ["Комплектовщик", "Оператор погрузчика", "Контролёр ОТК"],
    })


@pytest.fixture()
def sample_events_df() -> pd.DataFrame:
    return pd.DataFrame({
        "operation_name": ["Комплектация заказа", "Погрузка паллеты", "Проверка качества"],
        "event_count": [100, 80, 60],
        "avg_duration_sec": [450.0, 200.0, 300.0],
        "total_duration_sec": [45000, 16000, 18000],
    })


@pytest.fixture()
def sample_anomaly() -> AnomalyRecord:
    return AnomalyRecord(
        operation_name="Комплектация заказа",
        avg_duration_sec=450.0,
        norm_seconds=300,
        delta_sec=150.0,
        hourly_rate_rub=450.0,
        total_loss_rub=1875.0,
        event_count=100,
    )


@pytest.fixture()
def sample_report(sample_anomaly: AnomalyRecord, sample_events_df: pd.DataFrame) -> DailyReport:
    losses_df = pd.DataFrame({
        "operation_name": ["Комплектация заказа", "Проверка качества", "Погрузка паллеты"],
        "avg_duration_sec": [450.0, 300.0, 200.0],
        "avg_duration_min": [7.5, 5.0, 3.33],
        "norm_seconds": [300, 240, 180],
        "norm_min": [5.0, 4.0, 3.0],
        "delta_sec": [150.0, 60.0, 20.0],
        "hourly_rate_rub": [450.0, 480.0, 520.0],
        "event_count": [100, 60, 80],
        "loss_per_event_rub": [18.75, 8.0, 2.89],
        "total_loss_rub": [1875.0, 480.0, 231.11],
        "role_name": ["Комплектовщик", "Контролёр ОТК", "Оператор погрузчика"],
    })
    return DailyReport(
        report_date=datetime(2026, 2, 26, 6, 0),
        total_loss_rub=2586.11,
        total_events=240,
        losses_df=losses_df,
        top_anomalies=[sample_anomaly],
    )


# ── Моки внешних зависимостей ───────────────────────────

@pytest.fixture()
def mock_ch_client():
    """Мок ClickHouse клиента."""
    client = MagicMock()
    client.query.return_value = MagicMock(result_rows=[])
    client.command.return_value = None
    client.insert.return_value = None
    return client


@pytest.fixture()
def mock_pg_session():
    """Мок async PostgreSQL сессии."""
    session = AsyncMock()
    session.execute.return_value = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    return session
