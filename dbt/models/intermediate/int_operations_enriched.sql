{{ config(materialized='view') }}

/*
    Обогащение каждого события нормативами и ставками.
    Расчёт дельты и потери на уровне одного event.
*/

with events as (
    select * from {{ ref('stg_event_logs') }}
),

norms as (
    select * from {{ ref('stg_process_norms') }}
),

tariffs as (
    select * from {{ ref('stg_tariffs_fot') }}
),

enriched as (
    select
        e.case_id,
        e.operation_name,
        e.event_date,
        e.start_time,
        e.end_time,
        e.duration_seconds,
        e.user_id,

        n.norm_seconds,
        n.role_id,

        t.role_name,
        t.hourly_rate_rub,

        -- Дельта: насколько факт превышает норму (не меньше 0)
        greatest(toFloat64(e.duration_seconds) - toFloat64(n.norm_seconds), 0)
            as delta_sec,

        -- Потеря ФОТ на одно событие
        greatest(toFloat64(e.duration_seconds) - toFloat64(n.norm_seconds), 0)
            / 3600.0
            * t.hourly_rate_rub
            as loss_rub

    from events e
    inner join norms   n on e.operation_name = n.operation_name
    inner join tariffs t on n.role_id        = t.tariff_id
)

select * from enriched
