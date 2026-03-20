from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery = Celery(
    "processfix",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    task_track_started=True,
    worker_hijack_root_logger=False,
)

celery.autodiscover_tasks(["app.workers"])
