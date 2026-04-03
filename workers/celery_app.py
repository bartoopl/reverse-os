"""Celery worker configuration for async background tasks."""
from celery import Celery

from core.config import settings

celery_app = Celery(
    "reverseos",
    broker=str(settings.REDIS_URL),
    backend=str(settings.REDIS_URL),
    include=["workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,          # Only ack after task completes (no lost tasks on crash)
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1, # One task at a time per worker (prevents overload)
    beat_schedule={
        "poll-inpost-tracking": {
            "task": "workers.tasks.poll_tracking_updates",
            "schedule": 300.0,    # Every 5 minutes
        },
        "sync-ksef-references": {
            "task": "workers.tasks.sync_ksef_references",
            "schedule": 3600.0,   # Every hour
        },
    },
)
