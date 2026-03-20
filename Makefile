# ── ProcessFix AI — Makefile ────────────────────────────
# Послойное управление Data Platform через compose.

COMPOSE_DIR  := deploy/compose
BASE_FILE    := $(COMPOSE_DIR)/docker-compose.base.yml
DBT_FILE     := $(COMPOSE_DIR)/docker-compose.dbt.yml
AIRFLOW_FILE := $(COMPOSE_DIR)/docker-compose.airflow.yml
SCIENCE_FILE := $(COMPOSE_DIR)/docker-compose.science.yml
ENV_FILE     := .env

DC_BASE     := docker compose --env-file $(ENV_FILE) -f $(BASE_FILE)
DC_DBT      := $(DC_BASE) -f $(DBT_FILE)
DC_AIRFLOW  := $(DC_BASE) -f $(AIRFLOW_FILE)
DC_SCIENCE  := $(DC_BASE) -f $(SCIENCE_FILE)
DC_ALL      := $(DC_BASE) -f $(DBT_FILE) -f $(AIRFLOW_FILE) -f $(SCIENCE_FILE)

# ── Послойный запуск ────────────────────────────────────

.PHONY: up-base up-dbt up-airflow up-science up-all down ps

up-base:
	$(DC_BASE) up -d
	@echo "✅ Base layer: postgres, clickhouse, redis, minio"

up-dbt: up-base
	$(DC_DBT) up -d dbt-runner
	@echo "✅ dbt-runner ready (exec into container: make dbt-shell)"

up-airflow: up-base
	$(DC_AIRFLOW) up -d
	@echo "✅ Airflow: webserver http://localhost:8080 (admin/admin)"

up-science: up-base
	$(DC_SCIENCE) up -d jupyter
	@echo "✅ Jupyter: http://localhost:8888 (token from JUPYTER_TOKEN)"

up-all: up-base
	$(DC_ALL) up -d
	@echo "✅ Full platform: base + dbt + airflow + science"

down:
	$(DC_ALL) down --remove-orphans
	@echo "🛑 All services stopped."

ps:
	$(DC_ALL) ps

# ── dbt операции ────────────────────────────────────────

.PHONY: dbt-run dbt-test dbt-shell dbt-docs

dbt-run:
	docker exec processfix-dbt dbt run --target $${DBT_TARGET:-dev}

dbt-test:
	docker exec processfix-dbt dbt test --target $${DBT_TARGET:-dev}

dbt-shell:
	docker exec -it processfix-dbt /bin/bash

dbt-docs:
	docker exec processfix-dbt dbt docs generate --target $${DBT_TARGET:-dev}

# ── App CLI ─────────────────────────────────────────────

.PHONY: report sync-dims seed

report:
	python -m app.scripts.run_daily_report $(ARGS)

sync-dims:
	python -m app.scripts.sync_dims_to_clickhouse

seed:
	python -m app.db.seed

# ── Legacy MVP ──────────────────────────────────────────

.PHONY: up-legacy down-legacy

up-legacy:
	docker compose up -d
	@echo "✅ Legacy MVP: postgres, clickhouse, redis"

down-legacy:
	docker compose down

# ── Testing ─────────────────────────────────────────────

.PHONY: test test-cov

test:
	pytest -v

test-cov:
	pytest --cov=app --cov-report=term-missing

# ── Dev helpers ─────────────────────────────────────────

.PHONY: api logs

api:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

logs:
	$(DC_ALL) logs -f --tail=50
