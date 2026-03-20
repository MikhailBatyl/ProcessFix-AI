-- Проверка: нет event'ов с некорректной длительностью в staging.
-- Тест проходит, если запрос возвращает 0 строк.
select
    case_id,
    duration_seconds
from {{ ref('stg_event_logs') }}
where duration_seconds <= 0
   or duration_seconds >= 86400
