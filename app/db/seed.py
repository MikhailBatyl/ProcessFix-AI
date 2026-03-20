"""Seed-скрипт: заполняет Postgres справочниками, ClickHouse — тестовыми логами.

Запуск: ``python -m app.db.seed``
"""

import asyncio
import random
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.database import async_session_factory, get_ch_client
from app.db.models import ProcessNorm, TariffFOT

ROLES = [
    ("Комплектовщик", 450.0),
    ("Оператор погрузчика", 520.0),
    ("Контролёр ОТК", 480.0),
]

OPERATIONS = [
    ("Комплектация заказа", 300, "Комплектовщик"),
    ("Погрузка паллеты", 180, "Оператор погрузчика"),
    ("Проверка качества", 240, "Контролёр ОТК"),
    ("Маркировка товара", 120, "Комплектовщик"),
    ("Перемещение на склад", 200, "Оператор погрузчика"),
]


async def seed_postgres() -> dict[str, int]:
    async with async_session_factory() as session:
        existing = (await session.execute(select(TariffFOT))).scalars().all()
        if existing:
            print("[Seed PG] Справочники уже заполнены — пропуск.")
            role_map = {r.role_name: r.id for r in existing}
        else:
            role_map: dict[str, int] = {}
            for name, rate in ROLES:
                t = TariffFOT(role_name=name, hourly_rate_rub=rate)
                session.add(t)
                await session.flush()
                role_map[name] = t.id

            for op_name, norm_sec, role_name in OPERATIONS:
                n = ProcessNorm(
                    operation_name=op_name,
                    norm_seconds=norm_sec,
                    role_id=role_map[role_name],
                )
                session.add(n)

            await session.commit()
            print(f"[Seed PG] Создано ролей: {len(ROLES)}, нормативов: {len(OPERATIONS)}")

    return role_map


def seed_clickhouse(n_rows: int = 500) -> None:
    client = get_ch_client()

    existing = client.command("SELECT count() FROM event_logs")
    if existing > 0:
        print(f"[Seed CH] event_logs уже содержит {existing} строк — пропуск.")
        return

    op_names = [op[0] for op in OPERATIONS]
    norms = {op[0]: op[1] for op in OPERATIONS}

    now = datetime.utcnow()
    rows: list[list] = []

    for i in range(n_rows):
        op = random.choice(op_names)
        norm = norms[op]
        # ~70 % случаев — в пределах нормы (±20 %), ~30 % — аномалии (1.5x–3x)
        if random.random() < 0.7:
            actual = int(norm * random.uniform(0.8, 1.2))
        else:
            actual = int(norm * random.uniform(1.5, 3.0))

        start = now - timedelta(hours=random.uniform(0, 24))
        end = start + timedelta(seconds=actual)

        rows.append([
            f"CASE-{i:05d}",
            op,
            start,
            end,
            actual,
            f"USER-{random.randint(1, 20):03d}",
        ])

    columns = ["case_id", "operation_name", "start_time", "end_time", "duration_seconds", "user_id"]
    client.insert("event_logs", rows, column_names=columns)
    print(f"[Seed CH] Вставлено {n_rows} строк в event_logs.")


EQUIPMENT = [
    ("EQ-001", "Конвейер-1"),
    ("EQ-002", "Погрузчик-А"),
    ("EQ-003", "Упаковочная линия"),
    ("EQ-004", "Конвейер-2"),
]

SCADA_METRICS = [
    ("temperature_c", "°C", 20.0, 85.0),
    ("vibration_mm_s", "mm/s", 0.5, 12.0),
    ("speed_m_min", "m/min", 5.0, 30.0),
    ("motor_current_a", "A", 2.0, 25.0),
    ("pressure_bar", "bar", 1.0, 8.0),
]

EQUIPMENT_STATES = ["running", "running", "running", "idle", "warning", "maintenance"]


def seed_scada_telemetry(n_rows: int = 2000) -> None:
    client = get_ch_client()

    existing = client.command("SELECT count() FROM scada_telemetry")
    if existing > 0:
        print(f"[Seed CH] scada_telemetry уже содержит {existing} строк — пропуск.")
        return

    now = datetime.utcnow()
    rows: list[list] = []

    for i in range(n_rows):
        eq_id, eq_name = random.choice(EQUIPMENT)
        metric_name, unit, val_min, val_max = random.choice(SCADA_METRICS)

        if random.random() < 0.85:
            value = random.uniform(val_min, (val_min + val_max) / 2)
        else:
            value = random.uniform((val_min + val_max) / 2, val_max * 1.3)

        ts = now - timedelta(seconds=random.uniform(0, 86400))
        state = random.choice(EQUIPMENT_STATES)
        quality = 192 if random.random() < 0.95 else random.choice([0, 64, 128])

        rows.append([
            ts,
            eq_id,
            eq_name,
            metric_name,
            round(value, 2),
            unit,
            state,
            "scada",
            quality,
        ])

    columns = [
        "ts", "equipment_id", "equipment_name", "metric_name",
        "metric_value", "unit", "equipment_state", "source_system", "quality",
    ]
    client.insert("scada_telemetry", rows, column_names=columns)
    print(f"[Seed CH] Вставлено {n_rows} строк в scada_telemetry.")


async def main() -> None:
    await seed_postgres()
    seed_clickhouse()
    seed_scada_telemetry()


if __name__ == "__main__":
    asyncio.run(main())
