-- Проверка: нет отрицательных потерь в витрине.
select
    event_date,
    operation_name,
    total_loss_rub
from {{ ref('mart_daily_losses') }}
where total_loss_rub < 0
