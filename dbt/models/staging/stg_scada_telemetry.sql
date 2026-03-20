{{ config(materialized='view') }}

select
    ts,
    equipment_id,
    equipment_name,
    metric_name,
    metric_value,
    unit,
    equipment_state,
    source_system,
    quality,
    toDate(ts) as reading_date
from {{ source('raw', 'scada_telemetry') }}
where quality >= 64
  and metric_value is not null
