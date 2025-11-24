import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings

from wallets.WalletsAPI import WalletsAPI

logger = logging.getLogger(__name__)


class WalletScheduler:
    _instance = None
    _scheduler = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def start(self):
        if self._scheduler is not None:
            return

        from django_apscheduler.jobstores import DjangoJobStore
        
        self._scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
        self._scheduler.add_jobstore(DjangoJobStore(), "default")
        
        self._scheduler.add_job(
            self.fetchPolymarketWallets,
            trigger=CronTrigger(hour=0, minute=0),
            id="fetchPolymarketWallets",
            max_instances=1,
            replace_existing=True,
        )
        
        if settings.SCHEDULER_AUTOSTART:
            self._scheduler.start()
            logger.info("WalletScheduler started")

    def stop(self):
        if self._scheduler is not None:
            self._scheduler.shutdown()
            self._scheduler = None
            logger.info("WalletScheduler stopped")

    @staticmethod
    def fetchPolymarketWallets():
        try:
            logger.info("Starting scheduled Polymarket wallet fetch")
            walletsAPI = WalletsAPI()
            walletsAPI.fetchAllPolymarketCategories()
            logger.info("Completed scheduled Polymarket wallet fetch")
        except Exception as e:
            logger.error(f"Error in scheduled Polymarket wallet fetch: {str(e)}")

