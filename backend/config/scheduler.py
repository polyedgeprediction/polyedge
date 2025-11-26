"""
Centralized scheduler instance management.
Ensures EXACTLY ONE scheduler exists in the entire application.
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from threading import Lock

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler = None
_scheduler_lock = Lock()


def getScheduler() -> BackgroundScheduler:
    """
    Get the global scheduler instance.
    Creates and starts scheduler on first call.
    Returns existing scheduler on subsequent calls.
    
    Thread-safe singleton pattern.
    """
    global _scheduler
    
    if _scheduler is None:
        with _scheduler_lock:
            # Double-checked locking pattern
            if _scheduler is None:
                _scheduler = _createScheduler()
                _startScheduler()
                logger.info("SCHEDULER :: Created and started global scheduler instance")
    
    return _scheduler


def _createScheduler() -> BackgroundScheduler:
    """Create scheduler with Django integration"""
    jobStores = {
        'default': DjangoJobStore()  # Persists jobs in Django database
    }
    
    executors = {
        'default': ThreadPoolExecutor(max_workers=4)
    }
    
    jobDefaults = {
        'coalesce': True,           # Combine multiple pending executions
        'max_instances': 1,         # One instance per job
        'misfire_grace_time': 300   # 5 minute grace period
    }
    
    return BackgroundScheduler(
        jobstores=jobStores,
        executors=executors,
        job_defaults=jobDefaults,
        timezone='UTC'
    )


def _startScheduler() -> None:
    """Start the scheduler if not already running"""
    global _scheduler
    
    if _scheduler and not _scheduler.running:
        _scheduler.start()
        logger.info("SCHEDULER :: Started background scheduler")


def isSchedulerRunning() -> bool:
    """Check if scheduler is running"""
    global _scheduler
    return _scheduler is not None and _scheduler.running


def shutdownScheduler() -> None:
    """Graceful scheduler shutdown"""
    global _scheduler
    
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=True)
        logger.info("SCHEDULER :: Shutdown completed")
        _scheduler = None

