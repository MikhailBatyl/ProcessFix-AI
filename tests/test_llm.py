"""Unit-тесты для app.services.llm — генерация гипотез через OpenAI."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.analytics import AnomalyRecord
from app.services.llm import _fallback_text, generate_five_whys


class TestFallbackText:

    def test_contains_operation_name(self, sample_anomaly: AnomalyRecord):
        text = _fallback_text(sample_anomaly)
        assert sample_anomaly.operation_name in text
        assert "[AI-анализ недоступен]" in text


class TestGenerateFiveWhys:

    @pytest.mark.asyncio
    async def test_returns_fallback_when_no_api_key(self, sample_anomaly):
        with patch("app.services.llm.get_settings") as mock_settings:
            mock_settings.return_value.openai_api_key = ""

            result = await generate_five_whys(sample_anomaly)

            assert "[AI-анализ недоступен]" in result
            assert sample_anomaly.operation_name in result

    @pytest.mark.asyncio
    async def test_returns_llm_response_on_success(self, sample_anomaly):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="1. Гипотеза A\n2. Гипотеза B\n3. Гипотеза C"))]

        mock_client_instance = AsyncMock()
        mock_client_instance.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch("app.services.llm.get_settings") as mock_settings,
            patch("app.services.llm.AsyncOpenAI", return_value=mock_client_instance),
        ):
            mock_settings.return_value.openai_api_key = "sk-test"
            mock_settings.return_value.openai_model = "gpt-4o-mini"

            result = await generate_five_whys(sample_anomaly)

            assert "Гипотеза A" in result
            assert "Гипотеза C" in result

    @pytest.mark.asyncio
    async def test_returns_fallback_on_api_error(self, sample_anomaly):
        mock_client_instance = AsyncMock()
        mock_client_instance.chat.completions.create = AsyncMock(side_effect=Exception("API timeout"))

        with (
            patch("app.services.llm.get_settings") as mock_settings,
            patch("app.services.llm.AsyncOpenAI", return_value=mock_client_instance),
        ):
            mock_settings.return_value.openai_api_key = "sk-test"
            mock_settings.return_value.openai_model = "gpt-4o-mini"

            result = await generate_five_whys(sample_anomaly)

            assert "[AI-анализ недоступен]" in result
