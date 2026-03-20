"""Unit-тесты для app.services.telegram — отправка отчёта."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.telegram import send_report


class TestSendReport:

    @pytest.mark.asyncio
    async def test_skips_when_no_token(self):
        with patch("app.services.telegram.get_settings") as mock_settings:
            mock_settings.return_value.telegram_bot_token = ""
            mock_settings.return_value.telegram_chat_id = "123"

            result = await send_report(b"fake xlsx", 1000.0)
            assert result is False

    @pytest.mark.asyncio
    async def test_skips_when_no_chat_id(self):
        with patch("app.services.telegram.get_settings") as mock_settings:
            mock_settings.return_value.telegram_bot_token = "token123"
            mock_settings.return_value.telegram_chat_id = ""

            result = await send_report(b"fake xlsx", 1000.0)
            assert result is False

    @pytest.mark.asyncio
    async def test_sends_successfully(self):
        mock_bot_instance = AsyncMock()
        mock_bot_instance.send_document = AsyncMock(return_value=True)
        mock_bot_instance.session.close = AsyncMock()

        with (
            patch("app.services.telegram.get_settings") as mock_settings,
            patch("app.services.telegram.Bot", return_value=mock_bot_instance),
        ):
            mock_settings.return_value.telegram_bot_token = "token123"
            mock_settings.return_value.telegram_chat_id = "456"

            result = await send_report(b"fake xlsx", 1500.50)

            assert result is True
            mock_bot_instance.send_document.assert_called_once()
            call_kwargs = mock_bot_instance.send_document.call_args
            assert "1,500.50" in call_kwargs.kwargs["caption"] or "1500.50" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_returns_false_on_error(self):
        mock_bot_instance = AsyncMock()
        mock_bot_instance.send_document = AsyncMock(side_effect=Exception("Network error"))
        mock_bot_instance.session.close = AsyncMock()

        with (
            patch("app.services.telegram.get_settings") as mock_settings,
            patch("app.services.telegram.Bot", return_value=mock_bot_instance),
        ):
            mock_settings.return_value.telegram_bot_token = "token123"
            mock_settings.return_value.telegram_chat_id = "456"

            result = await send_report(b"fake xlsx", 1000.0)
            assert result is False

    @pytest.mark.asyncio
    async def test_custom_chat_id_overrides_env(self):
        mock_bot_instance = AsyncMock()
        mock_bot_instance.send_document = AsyncMock(return_value=True)
        mock_bot_instance.session.close = AsyncMock()

        with (
            patch("app.services.telegram.get_settings") as mock_settings,
            patch("app.services.telegram.Bot", return_value=mock_bot_instance),
        ):
            mock_settings.return_value.telegram_bot_token = "token123"
            mock_settings.return_value.telegram_chat_id = "default_id"

            result = await send_report(b"xlsx", 100.0, chat_id="999")

            assert result is True
            call_kwargs = mock_bot_instance.send_document.call_args
            assert call_kwargs.kwargs["chat_id"] == 999
