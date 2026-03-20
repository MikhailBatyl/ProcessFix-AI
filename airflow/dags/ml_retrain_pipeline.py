"""DAG: Калибровка нормативов (ML / Science pipeline).

Расписание: воскресенье 10:00 Asia/Novosibirsk.
Цепочка:
    run_norm_calibration_notebook → (опционально) notify

Запускает notebook `02_research/norm_calibration.ipynb` через papermill.
Notebook анализирует историю event_logs, рассчитывает рекомендуемые
нормативы (median + 0.5*std) и сохраняет CSV-артефакт в MinIO.

Нормативы НЕ применяются автоматически — только рекомендации.
Для автоприменения потребуется отдельный флаг / approval gate.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "processfix",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

NOTEBOOK_INPUT = "/opt/airflow/notebooks/02_research/norm_calibration.ipynb"
NOTEBOOK_OUTPUT = "/opt/airflow/notebooks/02_research/norm_calibration_output.ipynb"

PAPERMILL_PARAMS = " ".join([
    f'-p CLICKHOUSE_HOST "{os.getenv("CLICKHOUSE_HOST", "clickhouse")}"',
    f'-p CLICKHOUSE_PORT {os.getenv("CLICKHOUSE_PORT", "8123")}',
    f'-p CLICKHOUSE_DB "{os.getenv("CLICKHOUSE_DB", "processfix")}"',
    f'-p CLICKHOUSE_USER "{os.getenv("CLICKHOUSE_USER", "default")}"',
    f'-p CLICKHOUSE_PASSWORD "{os.getenv("CLICKHOUSE_PASSWORD", "")}"',
    f'-p MINIO_ENDPOINT "{os.getenv("MINIO_ENDPOINT", "minio:9000")}"',
    f'-p MINIO_ACCESS_KEY "{os.getenv("MINIO_ACCESS_KEY", "minioadmin")}"',
    f'-p MINIO_SECRET_KEY "{os.getenv("MINIO_SECRET_KEY", "minioadmin")}"',
    "-p LOOKBACK_DAYS 30",
    '-p OUTPUT_BUCKET "processfix-artifacts"',
    '-p OUTPUT_KEY "norm_calibration/{{ ds }}.csv"',
])

with DAG(
    dag_id="ml_retrain_pipeline",
    default_args=default_args,
    description="Калибровка нормативов: papermill → MinIO artifacts",
    schedule_interval="0 10 * * 0",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["processfix", "ml", "science"],
    max_active_runs=1,
) as dag:

    run_notebook = BashOperator(
        task_id="run_norm_calibration_notebook",
        bash_command=(
            f"papermill {NOTEBOOK_INPUT} {NOTEBOOK_OUTPUT} {PAPERMILL_PARAMS}"
        ),
    )

    notify = BashOperator(
        task_id="notify_completion",
        bash_command=(
            'echo "Norm calibration complete. Artifacts: s3://processfix-artifacts/norm_calibration/{{ ds }}.csv"'
        ),
    )

    run_notebook >> notify
