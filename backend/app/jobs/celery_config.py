from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue
from app.config import settings
import logging
import ssl

logger = logging.getLogger(__name__)

celery_app = Celery(
    "bidpilot",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30*60,
    task_soft_time_limit=25*60,
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
)

if settings.CELERY_BROKER_URL.startswith("rediss://"):
    celery_app.conf.broker_use_ssl = {"ssl_cert_reqs": ssl.CERT_REQUIRED}
if settings.CELERY_RESULT_BACKEND.startswith("rediss://"):
    celery_app.conf.redis_backend_use_ssl = {"ssl_cert_reqs": ssl.CERT_REQUIRED}

# Queue configuration
celery_app.conf.task_queues = (
    Queue("high_priority", Exchange("high_priority"), routing_key="high_priority"),
    Queue("default", Exchange("default"), routing_key="default"),
    Queue("low_priority", Exchange("low_priority"), routing_key="low_priority"),
)

# Default queue
celery_app.conf.task_default_queue = "default"
celery_app.conf.task_default_exchange = "default"
celery_app.conf.task_default_routing_key = "default"

# Periodic schedule (run `celery -A app.jobs.celery_config beat` alongside the worker)
celery_app.conf.beat_schedule = {
    "scan-tender-sources-hourly": {
        "task": "app.jobs.tasks.scan_tender_sources",
        "schedule": crontab(minute=0),          # top of every hour
        "options": {"queue": "low_priority"},
    },
    "scan-deadlines-daily": {
        "task": "app.jobs.tasks.scan_deadlines",
        "schedule": crontab(hour=6, minute=0),  # 06:00 UTC daily
        "options": {"queue": "low_priority"},
    },
}

# Ensure scheduled tasks are registered with the worker.
celery_app.conf.imports = ("app.jobs.tasks",)

logger.info("Celery configured")
