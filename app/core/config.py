from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── PostgreSQL ──────────────────────────────────────
    postgres_user: str = "processfix"
    postgres_password: str = "changeme"
    postgres_db: str = "processfix"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    @property
    def pg_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ── ClickHouse ──────────────────────────────────────
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_db: str = "processfix"
    clickhouse_user: str = "default"
    clickhouse_password: str = ""

    # ── Redis ───────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Telegram ────────────────────────────────────────
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # ── OpenAI ──────────────────────────────────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # ── MinIO (S3-compatible) ───────────────────────────
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_raw: str = "processfix-raw"
    minio_bucket_artifacts: str = "processfix-artifacts"
    minio_secure: bool = False

    # ── dbt ─────────────────────────────────────────────
    dbt_target: str = "dev"
    dbt_profiles_dir: str = "/dbt"

    # ── Airflow ─────────────────────────────────────────
    airflow_tz: str = "Asia/Novosibirsk"

    # ── Analytics ───────────────────────────────────────
    analytics_source: Literal["raw", "marts"] = "raw"

    # ── App ─────────────────────────────────────────────
    app_env: str = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
