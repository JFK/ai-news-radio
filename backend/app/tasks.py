import asyncio

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


@celery_app.task(name="run_pipeline_step")
def run_pipeline_step(episode_id: int, step_name: str) -> dict:
    """Execute a pipeline step asynchronously via Celery."""
    from app.database import async_session
    from app.models import StepName
    from app.pipeline import engine

    async def _run() -> None:
        async with async_session() as session:
            await engine.run_step(episode_id, StepName(step_name), session)

    asyncio.run(_run())
    return {"episode_id": episode_id, "step_name": step_name, "status": "completed"}
