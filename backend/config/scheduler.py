"""
Central scheduler configuration for the application.
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from django.conf import settings

logger = logging.getLogger(__name__)

_scheduler = None


def getScheduler():
    """Get or create the singleton scheduler instance."""
    global _scheduler
    
    if _scheduler is None:
        from django_apscheduler.jobstores import DjangoJobStore
        
        _scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
        _scheduler.add_jobstore(DjangoJobStore(), "default")
        
        if settings.SCHEDULER_AUTOSTART:
            _scheduler.start()
            logger.info("Scheduler started")
    
    return _scheduler

