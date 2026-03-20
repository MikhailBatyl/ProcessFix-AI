from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_ch_client, get_pg_session
from app.db.models import ProcessNorm, TariffFOT

router = APIRouter()


# ── Pydantic-схемы ──────────────────────────────────────

class TariffCreate(BaseModel):
    role_name: str
    hourly_rate_rub: float


class TariffOut(TariffCreate):
    id: int
    model_config = {"from_attributes": True}


class NormCreate(BaseModel):
    operation_name: str
    norm_seconds: int
    role_id: int


class NormOut(NormCreate):
    id: int
    model_config = {"from_attributes": True}


class EventLogRow(BaseModel):
    case_id: str
    operation_name: str
    start_time: datetime
    end_time: datetime
    duration_seconds: int
    user_id: str


class EventLogBatch(BaseModel):
    rows: list[EventLogRow]


class ScadaReading(BaseModel):
    ts: datetime
    equipment_id: str
    equipment_name: str = ""
    metric_name: str
    metric_value: float
    unit: str = ""
    equipment_state: str = "running"
    source_system: str = "scada"
    quality: int = 192


class ScadaBatch(BaseModel):
    readings: list[ScadaReading]


# ── Tariffs (ставки ФОТ) ────────────────────────────────

@router.post("/tariffs", response_model=TariffOut, status_code=status.HTTP_201_CREATED, tags=["справочники"])
async def create_tariff(
    payload: TariffCreate,
    session: AsyncSession = Depends(get_pg_session),
) -> TariffFOT:
    obj = TariffFOT(**payload.model_dump())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


@router.get("/tariffs", response_model=list[TariffOut], tags=["справочники"])
async def list_tariffs(
    session: AsyncSession = Depends(get_pg_session),
) -> list[TariffFOT]:
    result = await session.execute(select(TariffFOT))
    return list(result.scalars().all())


# ── Norms (нормативы операций) ───────────────────────────

@router.post("/norms", response_model=NormOut, status_code=status.HTTP_201_CREATED, tags=["справочники"])
async def create_norm(
    payload: NormCreate,
    session: AsyncSession = Depends(get_pg_session),
) -> ProcessNorm:
    role = await session.get(TariffFOT, payload.role_id)
    if not role:
        raise HTTPException(status_code=404, detail=f"Роль id={payload.role_id} не найдена")

    obj = ProcessNorm(**payload.model_dump())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


@router.get("/norms", response_model=list[NormOut], tags=["справочники"])
async def list_norms(
    session: AsyncSession = Depends(get_pg_session),
) -> list[ProcessNorm]:
    result = await session.execute(select(ProcessNorm))
    return list(result.scalars().all())


# ── Event Logs (загрузка логов в ClickHouse) ─────────────

@router.post("/events", status_code=status.HTTP_201_CREATED, tags=["логи"])
async def ingest_events(batch: EventLogBatch) -> dict[str, int]:
    if not batch.rows:
        raise HTTPException(status_code=400, detail="Пустой батч")

    client = get_ch_client()

    column_names = ["case_id", "operation_name", "start_time", "end_time", "duration_seconds", "user_id"]
    data = [
        [
            row.case_id,
            row.operation_name,
            row.start_time,
            row.end_time,
            row.duration_seconds,
            row.user_id,
        ]
        for row in batch.rows
    ]

    client.insert("event_logs", data, column_names=column_names)
    return {"inserted": len(data)}


# ── SCADA Telemetry (загрузка данных с датчиков) ─────────

@router.post("/scada", status_code=status.HTTP_201_CREATED, tags=["телеметрия"])
async def ingest_scada(batch: ScadaBatch) -> dict[str, int]:
    if not batch.readings:
        raise HTTPException(status_code=400, detail="Пустой батч")

    client = get_ch_client()

    column_names = [
        "ts", "equipment_id", "equipment_name", "metric_name",
        "metric_value", "unit", "equipment_state", "source_system", "quality",
    ]
    data = [
        [
            r.ts,
            r.equipment_id,
            r.equipment_name,
            r.metric_name,
            r.metric_value,
            r.unit,
            r.equipment_state,
            r.source_system,
            r.quality,
        ]
        for r in batch.readings
    ]

    client.insert("scada_telemetry", data, column_names=column_names)
    return {"inserted": len(data)}
