{{ config(materialized='view') }}

select
    case_id,
    operation_name,
    start_time,
    end_time,
    duration_seconds,
    user_id,
    toDate(start_time) as event_date
from {{ source('raw', 'event_logs') }}
where duration_seconds > 0
  and duration_seconds < 86400
