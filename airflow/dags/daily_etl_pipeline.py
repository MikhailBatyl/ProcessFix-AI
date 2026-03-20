"""DAG: Ежедневный ETL-пайплайн ProcessFix AI.

Расписание: 06:00 Asia/Novosibirsk (каждый день).
Цепочка:
    sync_dims → dbt_run → dbt_test → daily_report

Sync dims:  PG справочники → CH DIM-таблицы (чтобы dbt видел актуальные данные).
dbt run:    staging → intermediate → marts (mart_daily_losses).
dbt test:   schema + singular тесты.
Report:     analytics → llm → excel → telegram.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

AIRFLOW_TZ = os.getenv("AIRFLOW_TZ", "Asia/Novosibirsk")
DBT_TARGET = os.getenv("DBT_TARGET", "dev")
ANALYTICS_SOURCE = os.getenv("ANALYTICS_SOURCE", "raw")

default_args = {
    "owner": "processfix",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="daily_etl_pipeline",
    default_args=default_args,
    description="Ежедневный ETL: sync dims → dbt → отчёт → Telegram",
    schedule_interval="0 6 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["processfix", "daily", "etl"],
    max_active_runs=1,
) as dag:

    sync_dims = BashOperator(
        task_id="sync_dims_to_clickhouse",
        bash_command="python -m app.scripts.sync_dims_to_clickhouse",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd /opt/airflow/dbt 2>/dev/null || true && "
                     f"dbt run --target {DBT_TARGET} --profiles-dir /opt/airflow/dbt",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd /opt/airflow/dbt 2>/dev/null || true && "
                     f"dbt test --target {DBT_TARGET} --profiles-dir /opt/airflow/dbt",
    )

    daily_report = BashOperator(
        task_id="run_daily_report",
        bash_command=(
            'python -m app.scripts.run_daily_report --date "{{ ds }}"'
        ),
    )

    sync_dims >> dbt_run >> dbt_test >> daily_report
