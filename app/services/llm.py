"""Интеграция с OpenAI: генерация гипотез «5 Почему» для операционных аномалий."""

from __future__ import annotations

import logging

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.services.analytics import AnomalyRecord

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
Ты — эксперт по операционной эффективности на складах и производствах.
Тебе дают данные об операционной аномалии: название операции, фактическое среднее время,
нормативное время, и суммарные финансовые потери за день.

Твоя задача — предложить ровно 3 кратких гипотезы (каждая 1–2 предложения),
почему эта операция могла занять больше нормативного времени.
Используй метод «5 Почему» (5 Whys): каждая гипотеза должна копать глубже —
от симптома к корневой причине.

Формат ответа — нумерованный список:
1. …
2. …
3. …
"""

USER_TEMPLATE = """\
Аномалия: «{operation_name}»
Факт (ср.): {avg_sec:.0f} сек ({avg_min:.1f} мин)
Норма: {norm_sec} сек ({norm_min:.1f} мин)
Превышение: +{delta_sec:.0f} сек
Сумма потерь за день: {loss_rub:,.2f} ₽ ({event_count} событий)
"""


async def generate_five_whys(anomaly: AnomalyRecord) -> str:
    """Запросить у LLM 3 гипотезы «5 Почему» для одной аномалии.

    Возвращает отформатированный текст.
    При ошибке API возвращает строку-заглушку.
    """
    settings = get_settings()

    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY не задан — пропуск генерации гипотез.")
        return _fallback_text(anomaly)

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    user_msg = USER_TEMPLATE.format(
        operation_name=anomaly.operation_name,
        avg_sec=anomaly.avg_duration_sec,
        avg_min=anomaly.avg_duration_sec / 60,
        norm_sec=anomaly.norm_seconds,
        norm_min=anomaly.norm_seconds / 60,
        delta_sec=anomaly.delta_sec,
        loss_rub=anomaly.total_loss_rub,
        event_count=anomaly.event_count,
    )

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.7,
            max_tokens=500,
        )
        text = response.choices[0].message.content or ""
        logger.info("LLM: получены гипотезы для «%s»", anomaly.operation_name)
        return text.strip()

    except Exception:
        logger.exception("Ошибка при вызове OpenAI API")
        return _fallback_text(anomaly)


def _fallback_text(anomaly: AnomalyRecord) -> str:
    return (
        f"[AI-анализ недоступен]\n"
        f"Операция «{anomaly.operation_name}» превышает норму "
        f"на {anomaly.delta_sec:.0f} сек.\n"
        f"Рекомендуется ручной разбор корневых причин."
    )
