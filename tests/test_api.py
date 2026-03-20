"""Unit-тесты для app.api.routes — REST-эндпоинты.

Используем TestClient из FastAPI с замоканными зависимостями БД.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """TestClient с замоканным lifespan (без реальных PG/CH)."""
    with (
        patch("app.main.engine") as mock_engine,
        patch("app.main.ch_create_tables"),
    ):
        mock_conn = AsyncMock()
        mock_engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.begin.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_engine.dispose = AsyncMock()

        from app.main import app

        with TestClient(app) as c:
            yield c


class TestHealthCheck:

    def test_health_returns_ok(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestTariffsAPI:

    def test_create_tariff(self, client: TestClient):
        mock_session = AsyncMock()
        mock_obj = MagicMock(id=1, role_name="Тестовая роль", hourly_rate_rub=500.0)
        mock_session.refresh = AsyncMock(return_value=None)
        mock_session.commit = AsyncMock(return_value=None)
        mock_session.add = MagicMock()

        with patch("app.api.routes.get_pg_session") as mock_dep:
            async def fake_session():
                yield mock_session

            mock_dep.return_value = fake_session()

            resp = client.post("/api/v1/tariffs", json={
                "role_name": "Тестовая роль",
                "hourly_rate_rub": 500.0,
            })

        assert resp.status_code == 201

    def test_list_tariffs(self, client: TestClient):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("app.api.routes.get_pg_session") as mock_dep:
            async def fake_session():
                yield mock_session

            mock_dep.return_value = fake_session()

            resp = client.get("/api/v1/tariffs")

        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestEventsAPI:

    def test_ingest_events_empty_batch_returns_400(self, client: TestClient):
        resp = client.post("/api/v1/events", json={"rows": []})
        assert resp.status_code == 400

    def test_ingest_events_success(self, client: TestClient):
        with patch("app.api.routes.get_ch_client") as mock_ch:
            mock_client = MagicMock()
            mock_client.insert = MagicMock()
            mock_ch.return_value = mock_client

            resp = client.post("/api/v1/events", json={
                "rows": [{
                    "case_id": "CASE-001",
                    "operation_name": "Тест",
                    "start_time": "2026-02-26T08:00:00",
                    "end_time": "2026-02-26T08:05:00",
                    "duration_seconds": 300,
                    "user_id": "USER-001",
                }]
            })

        assert resp.status_code == 201
        assert resp.json()["inserted"] == 1
