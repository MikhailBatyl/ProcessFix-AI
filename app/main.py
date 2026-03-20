import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.database import engine
from app.db.models import Base
from app.db.clickhouse_ddl import create_tables as ch_create_tables
from app.api.routes import router as api_router

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("processfix")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.info("Создание таблиц PostgreSQL (если отсутствуют)…")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Создание таблиц ClickHouse (если отсутствуют)…")
    ch_create_tables()

    logger.info("ProcessFix AI запущен (%s)", settings.app_env)
    yield

    await engine.dispose()
    logger.info("ProcessFix AI остановлен.")


app = FastAPI(
    title="ProcessFix AI",
    description="Process Mining MVP — расчёт потерь ФОТ, Excel-отчёт, Telegram-доставка.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
