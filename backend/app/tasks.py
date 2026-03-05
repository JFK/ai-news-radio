from celery import Celery

from app.config import settings

celery_app = Celery("ai-news-radio", broker=settings.redis_url)
celery_app.conf.update(
    result_backend=settings.redis_url,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Tokyo",
)
