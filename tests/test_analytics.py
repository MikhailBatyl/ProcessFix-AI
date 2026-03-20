"""Unit-тесты для app.services.analytics — расчёт потерь и аномалий."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.services.analytics import (
    AnomalyRecord,
    DailyReport,
    _calculate_losses,
    _df_to_anomalies,
)


class TestCalculateLosses:
    """Тесты чистой функции _calculate_losses (без БД)."""

    def test_basic_loss_calculation(self, sample_events_df, sample_norms_df):
        result = _calculate_losses(sample_events_df, sample_norms_df)

        assert not result.empty
        assert "total_loss_rub" in result.columns
        assert "delta_sec" in result.columns
        assert all(result["delta_sec"] >= 0)
        assert all(result["total_loss_rub"] >= 0)

    def test_no_loss_when_under_norm(self, sample_norms_df):
        events = pd.DataFrame({
            "operation_name": ["Комплектация заказа"],
            "event_count": [50],
            "avg_duration_sec": [200.0],
            "total_duration_sec": [10000],
        })
        result = _calculate_losses(events, sample_norms_df)

        assert len(result) == 1
        assert result.iloc[0]["delta_sec"] == 0
        assert result.iloc[0]["total_loss_rub"] == 0

    def test_loss_formula_correctness(self, sample_norms_df):
        events = pd.DataFrame({
            "operation_name": ["Комплектация заказа"],
            "event_count": [1],
            "avg_duration_sec": [660.0],  # 360 sec over norm of 300
            "total_duration_sec": [660],
        })
        result = _calculate_losses(events, sample_norms_df)

        delta = 660.0 - 300
        expected_loss = round((delta / 3600) * 450.0 * 1, 2)
        assert result.iloc[0]["total_loss_rub"] == expected_loss

    def test_sorted_by_loss_descending(self, sample_events_df, sample_norms_df):
        result = _calculate_losses(sample_events_df, sample_norms_df)

        losses = result["total_loss_rub"].tolist()
        assert losses == sorted(losses, reverse=True)

    def test_empty_events_returns_empty(self, sample_norms_df):
        empty = pd.DataFrame(columns=["operation_name", "event_count", "avg_duration_sec", "total_duration_sec"])
        result = _calculate_losses(empty, sample_norms_df)
        assert result.empty

    def test_unmatched_operations_excluded(self, sample_norms_df):
        events = pd.DataFrame({
            "operation_name": ["Несуществующая операция"],
            "event_count": [10],
            "avg_duration_sec": [999.0],
            "total_duration_sec": [9990],
        })
        result = _calculate_losses(events, sample_norms_df)
        assert result.empty


class TestDfToAnomalies:

    def test_returns_correct_count(self, sample_events_df, sample_norms_df):
        losses_df = _calculate_losses(sample_events_df, sample_norms_df)
        anomalies = _df_to_anomalies(losses_df, top_n=2)

        assert len(anomalies) == 2
        assert all(isinstance(a, AnomalyRecord) for a in anomalies)

    def test_top1_is_highest_loss(self, sample_events_df, sample_norms_df):
        losses_df = _calculate_losses(sample_events_df, sample_norms_df)
        anomalies = _df_to_anomalies(losses_df, top_n=1)

        assert anomalies[0].total_loss_rub == losses_df.iloc[0]["total_loss_rub"]

    def test_empty_df_returns_empty(self):
        empty_df = pd.DataFrame()
        anomalies = _df_to_anomalies(empty_df, top_n=3)
        assert anomalies == []


class TestBuildDailyReportRaw:
    """Тест build_daily_report в raw-режиме с замоканными зависимостями."""

    @pytest.mark.asyncio
    async def test_returns_report_with_mocked_data(self, sample_events_df, sample_norms_df):
        with (
            patch("app.services.analytics.get_settings") as mock_settings,
            patch("app.services.analytics._load_norms_from_pg", return_value=sample_norms_df),
            patch("app.services.analytics._load_events_raw", return_value=sample_events_df),
        ):
            mock_settings.return_value.analytics_source = "raw"
            from app.services.analytics import build_daily_report

            report = await build_daily_report(top_n=3, report_date=datetime(2026, 2, 26))

            assert isinstance(report, DailyReport)
            assert report.total_loss_rub > 0
            assert report.total_events > 0
            assert len(report.top_anomalies) <= 3

    @pytest.mark.asyncio
    async def test_empty_events_returns_zero_report(self, sample_norms_df):
        empty_df = pd.DataFrame()
        with (
            patch("app.services.analytics.get_settings") as mock_settings,
            patch("app.services.analytics._load_norms_from_pg", return_value=sample_norms_df),
            patch("app.services.analytics._load_events_raw", return_value=empty_df),
        ):
            mock_settings.return_value.analytics_source = "raw"
            from app.services.analytics import build_daily_report

            report = await build_daily_report(report_date=datetime(2026, 2, 26))

            assert report.total_loss_rub == 0.0
            assert report.total_events == 0
            assert report.top_anomalies == []


class TestBuildDailyReportMarts:
    """Тест build_daily_report в marts-режиме."""

    @pytest.mark.asyncio
    async def test_marts_mode_reads_from_vitrina(self):
        mart_data = pd.DataFrame({
            "operation_name": ["Комплектация заказа"],
            "role_name": ["Комплектовщик"],
            "event_count": [100],
            "avg_duration_sec": [450.0],
            "norm_seconds": [300],
            "hourly_rate_rub": [450.0],
            "delta_sec": [150.0],
            "total_loss_rub": [1875.0],
        })
        mart_data["avg_duration_min"] = 7.5
        mart_data["norm_min"] = 5.0

        with (
            patch("app.services.analytics.get_settings") as mock_settings,
            patch("app.services.analytics._build_losses_marts", return_value=mart_data),
        ):
            mock_settings.return_value.analytics_source = "marts"
            from app.services.analytics import build_daily_report

            report = await build_daily_report(report_date=datetime(2026, 2, 26))

            assert report.total_loss_rub == 1875.0
            assert report.total_events == 100
            assert len(report.top_anomalies) == 1
            assert report.top_anomalies[0].operation_name == "Комплектация заказа"
