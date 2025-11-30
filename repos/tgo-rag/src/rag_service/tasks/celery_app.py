"""
Celery application configuration.

This module configures Celery for async document processing tasks.
It includes signal handlers to properly manage database connections
across forked worker processes.
"""

from celery import Celery
from celery.signals import worker_process_init, task_prerun

from ..config import get_settings

# Get settings
settings = get_settings()

# Create Celery app
celery_app = Celery(
    "rag_service",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "src.rag_service.tasks.document_processing",
        "src.rag_service.tasks.maintenance",
        "src.rag_service.tasks.website_crawling",
        "src.rag_service.tasks.qa_processing",
    ]
)

# Configure Celery
celery_app.conf.update(
    task_serializer=settings.celery_task_serializer,
    result_serializer=settings.celery_result_serializer,
    accept_content=["json"],
    result_expires=3600,
    timezone=settings.celery_timezone,
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Task routing
celery_app.conf.task_routes = {
    "src.rag_service.tasks.document_processing.*": {"queue": "document_processing"},
    "src.rag_service.tasks.embedding.*": {"queue": "embedding"},
    "src.rag_service.tasks.website_crawling.*": {"queue": "website_crawling"},
    "src.rag_service.tasks.qa_processing.*": {"queue": "qa_processing"},
    "crawl_website_task": {"queue": "celery"},  # Default queue for named task
    "process_qa_pair_task": {"queue": "celery"},  # Default queue for QA tasks
    "process_qa_pairs_batch_task": {"queue": "celery"},
}

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "cleanup-failed-tasks": {
        "task": "src.rag_service.tasks.maintenance.cleanup_failed_tasks",
        "schedule": 3600.0,  # Every hour
    },
}


# Signal handlers for managing database connections in forked workers
# 
# Problem: Celery prefork mode forks worker processes. When using SQLAlchemy
# async engines, the database connections are bound to a specific event loop.
# If a connection is created in one task, then the event loop closes, and a
# new task creates a new event loop, the old connections will fail with:
# - "RuntimeError: Event loop is closed"
# - "Future attached to a different loop"
#
# Solution: Reset database state when worker processes are initialized and
# before each task runs to ensure clean connections.

@worker_process_init.connect
def on_worker_process_init(**kwargs):
    """
    Called when a worker process is initialized (after fork).
    
    This ensures each worker starts with a clean database state,
    avoiding inherited connections from the parent process.
    """
    from ..database import reset_db_state
    reset_db_state()


@task_prerun.connect
def on_task_prerun(task_id, task, args, kwargs, **rest):
    """
    Called before each task is executed.
    
    This ensures database connections are reset before running any task,
    preventing 'Future attached to a different loop' errors when tasks
    create new event loops.
    """
    from ..database import reset_db_state
    reset_db_state()
