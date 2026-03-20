from collections.abc import AsyncGenerator

import clickhouse_connect
from clickhouse_connect.driver import Client as CHClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

# ── PostgreSQL (async) ──────────────────────────────────
engine = create_async_engine(
    settings.pg_dsn,
    echo=(settings.app_env == "development"),
    pool_size=10,
    max_overflow=20,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_pg_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


# ── ClickHouse (sync — clickhouse-connect) ──────────────
def get_ch_client() -> CHClient:
    return clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        database=settings.clickhouse_db,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
    )
