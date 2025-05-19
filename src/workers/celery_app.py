from celery import Celery
from models.settings import settings

celery_app = Celery(
    "aigym", broker=settings.redis_url, backend=settings.redis_url
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_max_tasks_per_child=100,
) 