# ProcessFix AI

**B2B SaaS-платформа класса Process Mining и операционной аналитики.**

Система принимает логи событий (event logs) со склада или производства (WMS / ERP) и телеметрию SCADA (датчики, состояния оборудования), рассчитывает финансовые потери ФОТ в рублях и ежедневно доставляет готовый Excel-отчёт руководителю через Telegram-бота. LLM (OpenAI) автоматически генерирует гипотезы корневых причин аномалий по методу «5 Почему».

---

## Архитектура

```
  WMS / ERP                          СКАДА (датчики)
      │                                    │
      │ POST /api/v1/events                │ POST /api/v1/scada
      ▼                                    ▼
┌──────────────────────────────────────────────────────────────────┐
│                         FastAPI (app/main.py)                    │
│  /health  /api/v1/tariffs  /api/v1/norms  /api/v1/events        │
│                                           /api/v1/scada          │
└────────┬──────────────────────────┬──────────────────────────────┘
         │                          │
    ┌────▼────┐              ┌──────▼──────────────────┐
    │PostgreSQL│              │       ClickHouse         │
    │  (OLTP)  │              │        (OLAP)            │
    │          │              │                          │
    │tariffs_fot│             │ event_logs  (WMS / ERP)  │
    │process_   │             │ scada_telemetry (СКАДА)  │
    │  norms    │             │ dim_*, mart_*            │
    └────┬─────┘              └──────┬───────────────────┘
         │                           │
         └───────────┬───────────────┘
                     │
         ┌───────────┼───────────────┐
         │                           │
  ┌──────▼──────┐            ┌───────▼─────────────┐
  │  analytics   │            │ dbt (ClickHouse)     │
  │   .py        │            │ staging → int → marts│
  └──────┬───────┘            └──────────────────────┘
         │
  ┌──────┼──────────┐
  │      │          │
┌─▼────┐ ┌▼──────┐ ┌▼───────┐
│llm.py│ │excel  │ │telegram│
│OpenAI│ │ .py   │ │  .py   │
│5 Whys│ │.xlsx  │ │ aiogram│
└──────┘ └───────┘ └────────┘
         │
  ┌──────▼──────┐
  │ Celery Beat  │  Ежедневный запуск
  │  + Redis     │  daily_report_job
  └──────────────┘
```

### Потоки данных

1. **Загрузка данных (WMS / ERP)** — внешние системы отправляют event-логи через `POST /api/v1/events` → ClickHouse `event_logs`.
2. **Загрузка данных (СКАДА)** — системы SCADA отправляют телеметрию датчиков и состояния оборудования через `POST /api/v1/scada` → ClickHouse `scada_telemetry`.
3. **Справочники** — нормативы и ставки ФОТ задаются через `POST /api/v1/tariffs` и `/norms` → PostgreSQL.
4. **Аналитика** — `analytics.py` агрегирует логи за 24 ч из ClickHouse, джойнит с нормативами из PostgreSQL, считает потери.
5. **AI-анализ** — для топ-1 аномалии `llm.py` запрашивает у OpenAI 3 гипотезы по методу «5 Почему».
6. **Excel-отчёт** — `excel.py` генерирует `.xlsx` с 3 листами: «Пульс», «Потери ФОТ», «AI Анализ».
7. **Доставка** — `telegram.py` отправляет файл в Telegram-чат руководителю.
8. **Расписание** — Celery Beat запускает `daily_report_job` каждый день в заданное время.
9. **dbt-трансформация** — SCADA-данные проходят через `stg_scada_telemetry` → `int_scada_daily_stats` → `mart_equipment_health`.

---

## Технологический стек

| Компонент | Технология | Назначение |
|-----------|-----------|------------|
| Web API | FastAPI + Uvicorn | REST-эндпоинты, вебхуки |
| OLTP-хранилище | PostgreSQL 16 + SQLAlchemy 2.0 (asyncpg) | Справочники: ставки, нормативы |
| OLAP-хранилище | ClickHouse 24 (clickhouse-connect) | Event-логи, SCADA-телеметрия, витрины |
| Очередь задач | Celery 5 + Redis 7 | Фоновые задачи, расписание (Beat) |
| Аналитика | pandas | Джойн, расчёт потерь, агрегации |
| Отчёты | openpyxl | Генерация стилизованного Excel |
| Доставка | aiogram 3.x | Отправка файлов через Telegram Bot |
| LLM | OpenAI API (gpt-4o-mini) | Генерация гипотез «5 Почему» |
| Конфигурация | pydantic-settings | Типизированные настройки из `.env` |

---

## Структура проекта

```
processfix-ai/
├── app/
│   ├── api/
│   │   └── routes.py           # CRUD: ставки, нормативы, загрузка логов
│   ├── core/
│   │   ├── config.py           # Pydantic Settings (PG, CH, Redis, MinIO, dbt, Airflow)
│   │   └── database.py         # Подключения: async PG engine + CH sync client
│   ├── db/
│   │   ├── models.py           # SQLAlchemy: TariffFOT, ProcessNorm
│   │   ├── clickhouse_ddl.py   # DDL: event_logs, scada_telemetry, dim_*, mart_*
│   │   └── seed.py             # Тестовые данные (3 роли, 5 операций, 500 логов, 2000 SCADA)
│   ├── services/
│   │   ├── analytics.py        # Потери ФОТ, аномалии (raw / marts режим)
│   │   ├── llm.py              # OpenAI: генерация гипотез «5 Почему»
│   │   ├── excel.py            # Сборка .xlsx (3 листа) через openpyxl
│   │   └── telegram.py         # Отправка отчёта через aiogram
│   ├── scripts/
│   │   ├── run_daily_report.py # CLI: полный пайплайн отчёта
│   │   └── sync_dims_to_clickhouse.py  # CLI: PG справочники → CH DIM-таблицы
│   ├── workers/
│   │   ├── celery_app.py       # Конфигурация Celery (Redis broker)
│   │   └── tasks.py            # Задача daily_report_job
│   └── main.py                 # Точка входа FastAPI (lifespan: создание таблиц)
├── deploy/
│   ├── compose/
│   │   ├── docker-compose.base.yml     # PG + CH + Redis + MinIO
│   │   ├── docker-compose.dbt.yml      # dbt-runner контейнер
│   │   ├── docker-compose.airflow.yml  # Airflow (CeleryExecutor)
│   │   └── docker-compose.science.yml  # Jupyter Lab
│   └── dockerfiles/
│       ├── Dockerfile.airflow          # Airflow + app зависимости
│       └── Dockerfile.dbt             # dbt-core + clickhouse adapter
├── airflow/dags/               # DAG'и Airflow (daily_etl, weekly, ml_retrain)
├── dbt/                        # dbt-проект (staging → intermediate → marts)
├── notebooks/                  # Jupyter: EDA, калибровка норм, исследования
├── tests/
│   ├── conftest.py             # Фикстуры, моки PG/CH
│   ├── test_analytics.py       # Тесты расчёта потерь (raw + marts)
│   ├── test_excel.py           # Тесты генерации xlsx
│   ├── test_llm.py             # Тесты OpenAI (mock)
│   ├── test_telegram.py        # Тесты Telegram-отправки (mock)
│   └── test_api.py             # Тесты REST API (TestClient)
├── docker-compose.yml          # Legacy MVP: postgres + clickhouse + redis
├── Makefile                    # Послойное управление платформой
├── pyproject.toml              # pytest конфигурация
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Схема баз данных

### PostgreSQL (справочники)

```sql
-- Ставки ФОТ по ролям
CREATE TABLE tariffs_fot (
    id              SERIAL PRIMARY KEY,
    role_name       VARCHAR(256) NOT NULL UNIQUE,
    hourly_rate_rub FLOAT        NOT NULL
);

-- Нормативы длительности операций
CREATE TABLE process_norms (
    id              SERIAL PRIMARY KEY,
    operation_name  VARCHAR(512) NOT NULL UNIQUE,
    norm_seconds    INTEGER      NOT NULL,
    role_id         INTEGER      NOT NULL REFERENCES tariffs_fot(id)
);
```

### ClickHouse (логи, телеметрия, DIM-таблицы, витрины)

```sql
-- Сырые логи событий (WMS / ERP)
CREATE TABLE event_logs (
    case_id          String,
    operation_name   String,
    start_time       DateTime,
    end_time         DateTime,
    duration_seconds Int32,
    user_id          String
)
ENGINE = MergeTree()
ORDER BY (operation_name, start_time)
PARTITION BY toYYYYMM(start_time);

-- Сырая телеметрия СКАДА (датчики, состояния оборудования)
CREATE TABLE scada_telemetry (
    ts              DateTime64(3),   -- метка времени (мс)
    equipment_id    String,          -- ID оборудования
    equipment_name  String,          -- название оборудования
    metric_name     String,          -- temperature_c, vibration_mm_s, …
    metric_value    Float64,         -- числовое показание
    unit            String,          -- единица измерения (°C, mm/s, …)
    equipment_state LowCardinality(String) DEFAULT 'running',
    source_system   LowCardinality(String) DEFAULT 'scada',
    quality         UInt8 DEFAULT 192  -- OPC UA quality (192 = Good)
)
ENGINE = MergeTree()
ORDER BY (equipment_id, metric_name, ts)
PARTITION BY toYYYYMM(ts)
TTL toDateTime(ts) + INTERVAL 1 YEAR;

-- DIM: нормативы (синхронизируются из PG)
CREATE TABLE dim_process_norms (
    id Int32, operation_name String,
    norm_seconds Int32, role_id Int32,
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at) ORDER BY id;

-- DIM: ставки ФОТ (синхронизируются из PG)
CREATE TABLE dim_tariffs_fot (
    id Int32, role_name String,
    hourly_rate_rub Float64,
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at) ORDER BY id;

-- Витрина: ежедневные потери (заполняется dbt)
CREATE TABLE mart_daily_losses (
    event_date Date, operation_name String,
    role_name String, event_count Int64,
    avg_duration_sec Float64, norm_seconds Int32,
    hourly_rate_rub Float64, delta_sec Float64,
    total_loss_rub Float64
) ENGINE = ReplacingMergeTree()
ORDER BY (event_date, operation_name)
PARTITION BY toYYYYMM(event_date);

-- Витрина: здоровье оборудования (заполняется dbt из SCADA)
CREATE TABLE mart_equipment_health (
    reading_date Date, equipment_id String,
    equipment_name String, metric_name String,
    unit String, reading_count Int64,
    avg_value Float64, min_value Float64,
    max_value Float64, stddev_value Float64,
    warning_count Int64, maintenance_count Int64,
    idle_count Int64, has_issues UInt8
) ENGINE = ReplacingMergeTree()
ORDER BY (reading_date, equipment_id, metric_name)
PARTITION BY toYYYYMM(reading_date);
```

---

## Бизнес-логика

### Расчёт потерь ФОТ

```
Дельта = max(0, Факт_средняя_длительность - Норма)
Потеря_на_событие = (Дельта / 3600) × Ставка_руб_час
Суммарная_потеря  = Потеря_на_событие × Кол-во_событий
```

### Поиск аномалий

1. Группировка `event_logs` по `operation_name` за последние 24 часа.
2. Расчёт средней длительности и суммарных потерь для каждой операции.
3. Сортировка по убыванию потерь. **Топ-3** = главные аномалии дня.

### AI-анализ (5 Whys)

Для аномалии #1 отправляется запрос в OpenAI API с контекстом:
- название операции, фактическое/нормативное время, сумма потерь.

LLM возвращает 3 гипотезы в формате нумерованного списка.
Если API недоступен — используется текстовая заглушка (graceful fallback).

---

## Быстрый старт

### Предварительные требования

- **Docker** и **Docker Compose** (для PostgreSQL, ClickHouse, Redis)
- **Python 3.11+**
- (Опционально) Telegram Bot Token и OpenAI API Key

### Шаг 1. Клонирование и настройка окружения

```bash
git clone <repo-url> processfix-ai
cd processfix-ai

# Создать файл переменных окружения
cp .env.example .env
# Отредактировать .env — задать свои ключи (Telegram, OpenAI)
```

### Шаг 2. Запуск инфраструктуры

```bash
docker compose up -d
```

Будут подняты три контейнера:

| Контейнер | Порт | Назначение |
|-----------|------|------------|
| `processfix-postgres` | 5432 | PostgreSQL 16 |
| `processfix-clickhouse` | 8123, 9000 | ClickHouse 24 |
| `processfix-redis` | 6379 | Redis 7 |

Проверить здоровье контейнеров:

```bash
docker compose ps
```

### Шаг 3. Установка Python-зависимостей

```bash
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### Шаг 4. Запуск API-сервера

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

При первом запуске автоматически создаются:
- Таблицы в PostgreSQL (`tariffs_fot`, `process_norms`)
- Таблица в ClickHouse (`event_logs`)

Swagger UI доступен по адресу: **http://localhost:8000/docs**

### Шаг 5. Заполнение тестовыми данными

```bash
python -m app.db.seed
```

Seed-скрипт создаст:
- **3 роли** (Комплектовщик, Оператор погрузчика, Контролёр ОТК)
- **5 нормативов** операций с привязкой к ролям
- **500 записей** в `event_logs` (~30% аномалий для наглядности)
- **2000 записей** в `scada_telemetry` (4 ед. оборудования, 5 метрик: температура, вибрация, скорость, ток, давление)

### Шаг 6. Запуск Celery Worker + Beat

```bash
# Worker (обработка задач)
celery -A app.workers.celery_app worker --loglevel=info

# Beat (расписание — в отдельном терминале)
celery -A app.workers.celery_app beat --loglevel=info
```

---

## CLI-команды

Скрипты в `app/scripts/` предоставляют CLI-интерфейс для Airflow и ручного запуска.

### Генерация ежедневного отчёта

```bash
# Отчёт за сегодня (источник определяется ANALYTICS_SOURCE)
python -m app.scripts.run_daily_report

# Отчёт за конкретную дату
python -m app.scripts.run_daily_report --date 2026-02-25

# С указанием chat_id (вместо значения из .env)
python -m app.scripts.run_daily_report --date 2026-02-25 --chat-id 123456789
```

Пайплайн: `analytics → llm (top-1 anomaly) → excel → telegram`.

### Синхронизация справочников PG → ClickHouse

```bash
python -m app.scripts.sync_dims_to_clickhouse
```

Выгружает `tariffs_fot` и `process_norms` из PostgreSQL в ClickHouse DIM-таблицы
(`dim_tariffs_fot`, `dim_process_norms`). Используется перед `dbt run`, чтобы
dbt мог джойнить нормативы с событиями внутри одного движка.

---

## Data Platform (послойный запуск)

Вся инфраструктура разделена на независимые слои, каждый поднимается отдельно через Makefile.

### Предварительные требования

- Docker и Docker Compose v2
- GNU Make (для Windows — через Git Bash, WSL2 или `choco install make`)

### Послойные команды

```bash
cp .env.example .env    # одноразовая настройка

make up-base            # PG + CH + Redis + MinIO
make up-dbt             # + dbt-runner контейнер
make up-airflow         # + Airflow (webserver, scheduler, worker)
make up-science         # + Jupyter Lab
make up-all             # все слои разом

make down               # остановить всё
make ps                 # статус контейнеров
```

### Доступ к сервисам

| Сервис | URL | Credentials |
|--------|-----|-------------|
| Swagger (API) | http://localhost:8000/docs | — |
| Airflow UI | http://localhost:8080 | admin / admin |
| Jupyter Lab | http://localhost:8888 | token = `JUPYTER_TOKEN` из .env |
| MinIO Console | http://localhost:9001 | minioadmin / minioadmin |
| ClickHouse HTTP | http://localhost:8123 | — |

### dbt-операции

```bash
make dbt-run            # dbt run --target dev
make dbt-test           # dbt test --target dev
make dbt-shell          # bash в dbt-runner контейнере
make dbt-docs           # dbt docs generate
```

### Архитектурные решения

**Почему CeleryExecutor для Airflow?** Redis уже есть в стеке. CeleryExecutor позволяет масштабировать worker'ы горизонтально и переиспользует существующую инфраструктуру.

**Почему metadata DB Airflow в общем Postgres?** В dev-окружении нет смысла поднимать отдельный PG. Airflow использует отдельную database `airflow` в том же контейнере. В production рекомендуется вынести в отдельный PG-инстанс.

**Почему MinIO, а не S3?** Локальный dev без зависимости от AWS. В production можно прозрачно переключить на S3 через endpoint.

---

## Режим источника данных (ANALYTICS_SOURCE)

Настройка `ANALYTICS_SOURCE` в `.env` переключает, откуда `analytics.py` берёт данные:

| Значение | Описание | Когда использовать |
|----------|----------|--------------------|
| `raw` (default) | MVP-путь: агрегация `event_logs` из CH + нормативы из PG, джойн в pandas | Legacy MVP, до настройки dbt |
| `marts` | Чтение готовой витрины `mart_daily_losses` из CH | После настройки dbt-пайплайна |

Публичный интерфейс `build_daily_report()` одинаков в обоих режимах —
вся переключающая логика инкапсулирована внутри модуля.

---

## API-эндпоинты

### Системные

| Метод | URL | Описание |
|-------|-----|----------|
| `GET` | `/health` | Health check |

### Справочники (`/api/v1`)

| Метод | URL | Описание |
|-------|-----|----------|
| `POST` | `/api/v1/tariffs` | Создать ставку ФОТ |
| `GET` | `/api/v1/tariffs` | Список всех ставок |
| `POST` | `/api/v1/norms` | Создать норматив операции |
| `GET` | `/api/v1/norms` | Список всех нормативов |

### Логи событий (WMS / ERP)

| Метод | URL | Описание |
|-------|-----|----------|
| `POST` | `/api/v1/events` | Батч-загрузка event-логов в ClickHouse |

### Телеметрия SCADA

| Метод | URL | Описание |
|-------|-----|----------|
| `POST` | `/api/v1/scada` | Батч-загрузка показаний датчиков и состояний оборудования |

### Примеры запросов

**Создание ставки:**
```bash
curl -X POST http://localhost:8000/api/v1/tariffs \
  -H "Content-Type: application/json" \
  -d '{"role_name": "Комплектовщик", "hourly_rate_rub": 450.0}'
```

**Создание норматива:**
```bash
curl -X POST http://localhost:8000/api/v1/norms \
  -H "Content-Type: application/json" \
  -d '{"operation_name": "Комплектация заказа", "norm_seconds": 300, "role_id": 1}'
```

**Загрузка логов событий (WMS / ERP):**
```bash
curl -X POST http://localhost:8000/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{
    "rows": [
      {
        "case_id": "CASE-00001",
        "operation_name": "Комплектация заказа",
        "start_time": "2026-02-26T08:00:00",
        "end_time": "2026-02-26T08:07:30",
        "duration_seconds": 450,
        "user_id": "USER-001"
      }
    ]
  }'
```

**Загрузка телеметрии SCADA (датчики, оборудование):**
```bash
curl -X POST http://localhost:8000/api/v1/scada \
  -H "Content-Type: application/json" \
  -d '{
    "readings": [
      {
        "ts": "2026-02-26T08:00:00.123",
        "equipment_id": "EQ-001",
        "equipment_name": "Конвейер-1",
        "metric_name": "temperature_c",
        "metric_value": 42.7,
        "unit": "°C",
        "equipment_state": "running",
        "source_system": "scada",
        "quality": 192
      },
      {
        "ts": "2026-02-26T08:00:00.456",
        "equipment_id": "EQ-002",
        "equipment_name": "Погрузчик-А",
        "metric_name": "vibration_mm_s",
        "metric_value": 7.3,
        "unit": "mm/s",
        "equipment_state": "warning",
        "source_system": "scada",
        "quality": 192
      }
    ]
  }'
```

---

## Excel-отчёт (3 листа)

Генерируемый `.xlsx` файл содержит:

| Лист | Содержимое |
|------|-----------|
| **Пульс** | Сводные KPI: суммарные потери (₽), кол-во операций, кол-во аномалий, топ-аномалия |
| **Потери ФОТ** | Таблица: Операция, Факт (мин), Норма (мин), Дельта (сек), Ставка (₽/ч), Событий, Сумма потерь (₽) |
| **AI Анализ** | Название операции-аномалии, метрики, 3 гипотезы «5 Почему» от LLM |

Оформление: корпоративные цвета, стилизованные заголовки, рамки, авто-ширина столбцов, форматирование валюты.

---

## Конфигурация (.env)

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `POSTGRES_USER` | `processfix` | Пользователь PostgreSQL |
| `POSTGRES_PASSWORD` | `changeme` | Пароль PostgreSQL |
| `POSTGRES_DB` | `processfix` | Имя базы данных |
| `POSTGRES_HOST` | `localhost` | Хост PostgreSQL |
| `POSTGRES_PORT` | `5432` | Порт PostgreSQL |
| `CLICKHOUSE_HOST` | `localhost` | Хост ClickHouse |
| `CLICKHOUSE_PORT` | `8123` | HTTP-порт ClickHouse |
| `CLICKHOUSE_DB` | `processfix` | Имя базы данных CH |
| `CLICKHOUSE_USER` | `default` | Пользователь CH |
| `CLICKHOUSE_PASSWORD` | *(пустой)* | Пароль CH |
| `REDIS_URL` | `redis://localhost:6379/0` | URL подключения к Redis |
| `TELEGRAM_BOT_TOKEN` | — | Токен Telegram-бота |
| `TELEGRAM_CHAT_ID` | — | ID чата для отправки отчёта |
| `OPENAI_API_KEY` | — | API-ключ OpenAI |
| `OPENAI_MODEL` | `gpt-4o-mini` | Модель OpenAI |
| `MINIO_ENDPOINT` | `localhost:9000` | Эндпоинт MinIO (S3) |
| `MINIO_ACCESS_KEY` | `minioadmin` | Access Key MinIO |
| `MINIO_SECRET_KEY` | `minioadmin` | Secret Key MinIO |
| `MINIO_BUCKET_RAW` | `processfix-raw` | Бакет для сырых файлов |
| `MINIO_BUCKET_ARTIFACTS` | `processfix-artifacts` | Бакет для артефактов (dbt, notebooks) |
| `DBT_TARGET` | `dev` | dbt target (dev / prod) |
| `DBT_PROFILES_DIR` | `/dbt` | Путь к profiles.yml |
| `AIRFLOW_TZ` | `Asia/Novosibirsk` | Таймзона Airflow |
| `ANALYTICS_SOURCE` | `raw` | Источник данных: `raw` (MVP) или `marts` (dbt) |
| `APP_ENV` | `development` | Окружение (development / production) |
| `LOG_LEVEL` | `INFO` | Уровень логирования |

---

## Тестирование

### Запуск unit-тестов

```bash
# Все тесты (без живых БД — всё замокировано)
pytest

# С покрытием
pytest --cov=app --cov-report=term-missing

# Конкретный модуль
pytest tests/test_analytics.py -v
```

### Что покрыто тестами

| Модуль | Файл теста | Что проверяется |
|--------|-----------|-----------------|
| `analytics.py` | `test_analytics.py` | Формула потерь, clip delta>=0, сортировка, пустые данные, raw/marts режимы |
| `excel.py` | `test_excel.py` | 3 листа присутствуют, KPI-значения на «Пульс», заголовки таблицы, AI-текст, пустой отчёт |
| `llm.py` | `test_llm.py` | Fallback без API-ключа, успешный ответ LLM (mock), ошибка API → fallback |
| `telegram.py` | `test_telegram.py` | Пропуск без токена/chat_id, успешная отправка, ошибка сети, override chat_id |
| `api/routes.py` | `test_api.py` | `/health`, POST/GET tariffs, POST events (пустой батч = 400, валидный = 201) |

### Добавление Makefile-цели

```bash
make test          # (добавьте в Makefile при необходимости)
```

---

## Airflow DAGs

| DAG | Расписание | Цепочка задач |
|-----|-----------|---------------|
| `daily_etl_pipeline` | 06:00 ежедневно | sync_dims → dbt run → dbt test → daily_report |
| `weekly_report_pipeline` | Пн 08:00 | sync_dims → dbt run → weekly_report |
| `ml_retrain_pipeline` | Вс 10:00 | papermill(norm_calibration.ipynb) → notify |

Все DAG'и используют `BashOperator` для вызова CLI-скриптов из `app/scripts/`.
Параметры (дата, target) передаются через Jinja-шаблоны Airflow (`{{ ds }}`).

---

## Definition of Done

| Критерий | Статус |
|----------|--------|
| Legacy MVP работает как раньше (API, Celery, docker-compose.yml) | Done |
| Data Platform поднимается послойно через Makefile | Done |
| `ANALYTICS_SOURCE=raw` — отчёт из raw event_logs + PG norms | Done |
| `ANALYTICS_SOURCE=marts` — отчёт из dbt-витрины `mart_daily_losses` | Done |
| dbt строит `mart_daily_losses` (staging → intermediate → marts) | Done |
| SCADA-телеметрия: ingestion → dbt → `mart_equipment_health` | Done |
| Airflow daily DAG: sync → dbt → report (end-to-end) | Done |
| Unit-тесты без живых БД (pytest, все сервисы замокированы) | Done |
| CLI entrypoints для Airflow-вызовов | Done |
| Jupyter notebook для калибровки нормативов (papermill-ready) | Done |

---

## Дальнейшее развитие

### Data Platform (в процессе)

- [x] CLI entrypoints для Airflow-вызовов
- [x] Режим `ANALYTICS_SOURCE=marts` (dbt-витрины)
- [x] DIM-таблицы в ClickHouse + sync-скрипт PG → CH
- [x] Multi-compose инфраструктура (base, airflow, dbt, science)
- [x] dbt-проект (staging → intermediate → marts)
- [x] Airflow DAGs (daily ETL, weekly reports, ML retrain)
- [x] Jupyter notebooks (EDA, калибровка норм)
- [x] MinIO (S3) для raw-файлов и артефактов
- [x] SCADA-телеметрия (ingestion API + dbt + mart_equipment_health)
- [x] Unit-тесты (pytest, без живых БД)

### Продукт (Фаза 2+)

- [ ] Веб-интерфейс (React / Next.js) с дашбордами
- [ ] Process Map визуализация (граф процесса)
- [ ] Автоматическое обнаружение bottleneck через BPMN-анализ
- [ ] Мультитенантность (несколько организаций)
- [ ] Подключение дополнительных источников данных (1С, SAP)
- [ ] Алертинг при превышении порогов потерь в реальном времени

---

## Лицензия

Проприетарная. Все права защищены.
