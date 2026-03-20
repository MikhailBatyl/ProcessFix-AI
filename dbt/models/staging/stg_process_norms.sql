{{ config(materialized='view') }}

-- FINAL дедуплицирует строки ReplacingMergeTree до последней версии
select
    id          as norm_id,
    operation_name,
    norm_seconds,
    role_id
from {{ source('dims', 'dim_process_norms') }} final
