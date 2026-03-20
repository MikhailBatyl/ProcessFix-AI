"""DDL-скрипты для создания таблиц ClickHouse.

Запуск: ``python -m app.db.clickhouse_ddl``
"""

from app.core.database import get_ch_client

EVENT_LOGS_DDL = """
CREATE TABLE IF NOT EXISTS event_logs (
    case_id       String,
    operation_name String,
    start_time    DateTime,
    end_time      DateTime,
    duration_seconds Int32,
    user_id       String
)
ENGINE = MergeTree()
ORDER BY (operation_name, start_time)
PARTITION BY toYYYYMM(start_time)
"""

DIM_TARIFFS_FOT_DDL = """
CREATE TABLE IF NOT EXISTS dim_tariffs_fot (
    id              Int32,
    role_name       String,
    hourly_rate_rub Float64,
    updated_at      DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY id
"""

DIM_PROCESS_NORMS_DDL = """
CREATE TABLE IF NOT EXISTS dim_process_norms (
    id              Int32,
    operation_name  String,
    norm_seconds    Int32,
    role_id         Int32,
    updated_at      DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY id
"""

MART_DAILY_LOSSES_DDL = """
CREATE TABLE IF NOT EXISTS mart_daily_losses (
    event_date       Date,
    operation_name   String,
    role_name        String,
    event_count      Int64,
    avg_duration_sec Float64,
    norm_seconds     Int32,
    hourly_rate_rub  Float64,
    delta_sec        Float64,
    total_loss_rub   Float64,
    z_score          Float64 DEFAULT 0
)
ENGINE = ReplacingMergeTree()
ORDER BY (event_date, operation_name)
PARTITION BY toYYYYMM(event_date)
"""

SCADA_TELEMETRY_DDL = """
CREATE TABLE IF NOT EXISTS scada_telemetry (
    ts              DateTime64(3),
    equipment_id    String,
    equipment_name  String,
    metric_name     String,
    metric_value    Float64,
    unit            String,
    equipment_state LowCardinality(String) DEFAULT 'running',
    source_system   LowCardinality(String) DEFAULT 'scada',
    quality         UInt8 DEFAULT 192
)
ENGINE = MergeTree()
ORDER BY (equipment_id, metric_name, ts)
PARTITION BY toYYYYMM(ts)
TTL toDateTime(ts) + INTERVAL 1 YEAR
"""

MART_EQUIPMENT_HEALTH_DDL = """
CREATE TABLE IF NOT EXISTS mart_equipment_health (
    reading_date       Date,
    equipment_id       String,
    equipment_name     String,
    metric_name        String,
    unit               String,
    reading_count      Int64,
    avg_value          Float64,
    min_value          Float64,
    max_value          Float64,
    stddev_value       Float64,
    warning_count      Int64 DEFAULT 0,
    maintenance_count  Int64 DEFAULT 0,
    idle_count         Int64 DEFAULT 0,
    has_issues         UInt8 DEFAULT 0
)
ENGINE = ReplacingMergeTree()
ORDER BY (reading_date, equipment_id, metric_name)
PARTITION BY toYYYYMM(reading_date)
"""

_ALL_DDL = [
    ("event_logs", EVENT_LOGS_DDL),
    ("scada_telemetry", SCADA_TELEMETRY_DDL),
    ("dim_tariffs_fot", DIM_TARIFFS_FOT_DDL),
    ("dim_process_norms", DIM_PROCESS_NORMS_DDL),
    ("mart_daily_losses", MART_DAILY_LOSSES_DDL),
    ("mart_equipment_health", MART_EQUIPMENT_HEALTH_DDL),
]


def create_tables() -> None:
    client = get_ch_client()
    for name, ddl in _ALL_DDL:
        client.command(ddl)
        print(f"[ClickHouse] Таблица {name} готова.")


if __name__ == "__main__":
    create_tables()
