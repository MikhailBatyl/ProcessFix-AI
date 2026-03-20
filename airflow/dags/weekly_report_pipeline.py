"""DAG: Еженедельный сводный отчёт ProcessFix AI.

Расписание: понедельник 08:00 Asia/Novosibirsk.
Цепочка: sync_dims → dbt_run → weekly_report

Недельный отчёт агрегирует потери за предыдущие 7 дней.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

DBT_TARGET = os.getenv("DBT_TARGET", "dev")

default_args = {
    "owner": "processfix",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="weekly_report_pipeline",
    default_args=default_args,
    description="Еженедельный сводный отчёт (Пн 08:00)",
    schedule_interval="0 8 * * 1",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["processfix", "weekly", "report"],
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

    weekly_report = BashOperator(
        task_id="run_weekly_report",
        bash_command=(
            # week_start = ds (execution_date) минус 7 дней = прошлый понедельник
            'python -m app.scripts.run_weekly_report '
            '--week-start "{{ (execution_date - macros.timedelta(days=7)).strftime(\'%Y-%m-%d\') }}"'
        ),
    )

    sync_dims >> dbt_run >> weekly_report
