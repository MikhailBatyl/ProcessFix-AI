{{
    config(
        materialized='table',
        engine='ReplacingMergeTree()',
        order_by='(event_date, operation_name)',
        partition_by='toYYYYMM(event_date)'
    )
}}

/*
    Ежедневная витрина потерь ФОТ по операциям.
    Агрегация из int_operations_enriched → одна строка на (event_date, operation_name).
    z_score показывает, насколько средняя длительность отклоняется от нормы
    относительно стандартного отклонения по всей дате.
*/

with daily_agg as (
    select
        event_date,
        operation_name,
        role_name,
        hourly_rate_rub,
        norm_seconds,

        count()                         as event_count,
        avg(duration_seconds)           as avg_duration_sec,
        stddevPop(duration_seconds)     as stddev_duration_sec,

        avg(delta_sec)                  as delta_sec,
        sum(loss_rub)                   as total_loss_rub

    from {{ ref('int_operations_enriched') }}
    group by
        event_date,
        operation_name,
        role_name,
        hourly_rate_rub,
        norm_seconds
),

with_zscore as (
    select
        *,
        -- Z-score: (avg - norm) / stddev; защита от деления на 0
        if(
            stddev_duration_sec > 0,
            (avg_duration_sec - norm_seconds) / stddev_duration_sec,
            0
        ) as z_score
    from daily_agg
)

select
    event_date,
    operation_name,
    role_name,
    event_count,
    round(avg_duration_sec, 2)   as avg_duration_sec,
    norm_seconds,
    hourly_rate_rub,
    round(delta_sec, 2)          as delta_sec,
    round(total_loss_rub, 2)     as total_loss_rub,
    round(z_score, 3)            as z_score
from with_zscore
