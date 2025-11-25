import logging
from apscheduler.triggers.cron import CronTrigger

from positions.schedulers.FetchNewWalletPositionsScheduler import FetchNewWalletPositionsScheduler

logger = logging.getLogger(__name__)


def configurePositionJobs(scheduler):
    """Configure all position-related scheduled jobs."""
    scheduler.add_job(
        fetchNewWalletPositions,
        trigger=CronTrigger(minute='*/30'),
        id="fetchNewWalletPositions",
        max_instances=1,
        replace_existing=True
    )
    logger.info("Position jobs configured")


def fetchNewWalletPositions():
    """Fetch positions for all NEW wallets."""
    try:
        logger.info("Starting scheduled fetch of positions for new wallets")
        FetchNewWalletPositionsScheduler.execute()
        logger.info("Completed scheduled fetch of positions for new wallets")
    except Exception as e:
        logger.error(f"Error in scheduled position fetch: {str(e)}", exc_info=True)

