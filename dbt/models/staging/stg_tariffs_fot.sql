{{ config(materialized='view') }}

select
    id              as tariff_id,
    role_name,
    hourly_rate_rub
from {{ source('dims', 'dim_tariffs_fot') }} final
