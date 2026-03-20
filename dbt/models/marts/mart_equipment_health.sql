{{
    config(
        materialized='table',
        engine='ReplacingMergeTree()',
        order_by='(reading_date, equipment_id, metric_name)',
        partition_by='toYYYYMM(reading_date)'
    )
}}

with stats as (
    select * from {{ ref('int_scada_daily_stats') }}
),

with_flags as (
    select
        reading_date,
        equipment_id,
        equipment_name,
        metric_name,
        unit,

        reading_count,
        round(avg_value, 3)    as avg_value,
        round(min_value, 3)    as min_value,
        round(max_value, 3)    as max_value,
        round(stddev_value, 3) as stddev_value,

        warning_count,
        maintenance_count,
        idle_count,

        if(warning_count + maintenance_count > 0, 1, 0) as has_issues
    from stats
)

select * from with_flags
