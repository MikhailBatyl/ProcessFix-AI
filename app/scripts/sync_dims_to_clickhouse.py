"""CLI: Синхронизация справочников PostgreSQL → ClickHouse DIM-таблицы.

Выгружает tariffs_fot и process_norms из PG и вставляет
в dim_tariffs_fot / dim_process_norms (ReplacingMergeTree).
Идемпотентна: повторные запуски корректно обновляют данные.

Запуск:
    python -m app.scripts.sync_dims_to_clickhouse

Airflow вызывает перед dbt run, чтобы dbt видел актуальные нормативы.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select

from app.core.database import async_session_factory, get_ch_client
from app.db.models import ProcessNorm, TariffFOT

logger = logging.getLogger("processfix.cli.sync_dims")


async def _load_tariffs() -> list[list]:
    async with async_session_factory() as session:
        rows = (await session.execute(select(TariffFOT))).scalars().all()
    now = datetime.utcnow()
    return [[r.id, r.role_name, r.hourly_rate_rub, now] for r in rows]


async def _load_norms() -> list[list]:
    async with async_session_factory() as session:
        rows = (await session.execute(select(ProcessNorm))).scalars().all()
    now = datetime.utcnow()
    return [[r.id, r.operation_name, r.norm_seconds, r.role_id, now] for r in rows]


async def sync() -> None:
    client = get_ch_client()

    tariff_rows = await _load_tariffs()
    if tariff_rows:
        client.insert(
            "dim_tariffs_fot",
            tariff_rows,
            column_names=["id", "role_name", "hourly_rate_rub", "updated_at"],
        )
        logger.info("dim_tariffs_fot: загружено %d строк", len(tariff_rows))
    else:
        logger.warning("PG tariffs_fot пуста — пропуск.")

    norm_rows = await _load_norms()
    if norm_rows:
        client.insert(
            "dim_process_norms",
            norm_rows,
            column_names=["id", "operation_name", "norm_seconds", "role_id", "updated_at"],
        )
        logger.info("dim_process_norms: загружено %d строк", len(norm_rows))
    else:
        logger.warning("PG process_norms пуста — пропуск.")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    logger.info("Синхронизация PG → CH DIMs…")
    asyncio.run(sync())
    logger.info("Готово.")


if __name__ == "__main__":
    main()
