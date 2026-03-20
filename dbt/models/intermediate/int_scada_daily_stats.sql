{{ config(materialized='view') }}

with telemetry as (
    select * from {{ ref('stg_scada_telemetry') }}
),

daily_stats as (
    select
        reading_date,
        equipment_id,
        equipment_name,
        metric_name,
        unit,

        count()              as reading_count,
        avg(metric_value)    as avg_value,
        min(metric_value)    as min_value,
        max(metric_value)    as max_value,
        stddevPop(metric_value) as stddev_value,

        countIf(equipment_state = 'warning')     as warning_count,
        countIf(equipment_state = 'maintenance')  as maintenance_count,
        countIf(equipment_state = 'idle')         as idle_count
    from telemetry
    group by reading_date, equipment_id, equipment_name, metric_name, unit
)

select * from daily_stats
