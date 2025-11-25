import logging
from apscheduler.triggers.cron import CronTrigger

from wallets.WalletsAPI import WalletsAPI

logger = logging.getLogger(__name__)


def configureWalletJobs(scheduler):
    """Configure all wallet-related scheduled jobs."""
    scheduler.add_job(
        fetchPolymarketWallets,
        trigger=CronTrigger(hour=0, minute=0),
        id="fetchPolymarketWallets",
        max_instances=1,
        replace_existing=True
    )
    logger.info("Wallet jobs configured")


def fetchPolymarketWallets():
    """Fetch top-performing wallets from Polymarket leaderboard."""
    try:
        logger.info("Starting scheduled Polymarket wallet fetch")
        walletsAPI = WalletsAPI()
        walletsAPI.fetchAllPolymarketCategories()
        logger.info("Completed scheduled Polymarket wallet fetch")
    except Exception as e:
        logger.error(f"Error in scheduled Polymarket wallet fetch: {str(e)}", exc_info=True)

