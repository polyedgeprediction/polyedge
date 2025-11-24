"""
WalletsAPI - Main entry point for fetching and persisting smart money wallets.
"""
import logging
from typing import List
from django.utils import timezone

from .FetchSmartMoneyWalletAction import FetchSmartMoneyWalletAction
from wallets.pojos.FetchSmartMoneyWalletAPIResponse import FetchSmartMoneyWalletAPIResponse
from wallets.SmartMoneyWalletPersistenceHandler import SmartMoneyWalletPersistenceHandler
from wallets.implementations.polymarket.Constants import TIME_PERIOD_MONTH, SMART_MONEY_CATEGORIES
from wallets.Constants import PLATFORM_POLYMARKET

logger = logging.getLogger(__name__)


class WalletsAPI:
    
    def __init__(self):
        self.action = FetchSmartMoneyWalletAction()
        self.handler = SmartMoneyWalletPersistenceHandler()
    
    def fetchAndPersist(self, platform: str, categories: List[str], timePeriod: str = TIME_PERIOD_MONTH) -> FetchSmartMoneyWalletAPIResponse:           
        try:
            logger.info("FETCH_WALLETS_API :: Fetching wallets from platform API for categories: %s and time period: %s", categories, timePeriod)
            response = self.action.fetchWallets(platform=platform, categories=categories, timePeriod=timePeriod)
            
            if not response.success:
                logger.info("FETCH_WALLETS_API :: Fetch failed | Error: %s", response.errorMessage)
                return FetchSmartMoneyWalletAPIResponse(success=False, errorMessage=response.errorMessage)
            
            if not response.hasWallets():
                logger.info("FETCH_WALLETS_API :: No wallets found for categories: %s", categories)
                return FetchSmartMoneyWalletAPIResponse(success=True, totalProcessed=0)

            logger.info("FETCH_WALLETS_API :: Fetch successful | Total wallets: %d", len(response.wallets))
            return self.handler.persistWallets(wallets=response.wallets, snapshotTime=timezone.now())
            
        except Exception as e:
            logger.info("FETCH_WALLETS_API :: Unexpected error | Platform: %s | Categories: %s | Error: %s", 
                        platform, categories, str(e), exc_info=True)
            return FetchSmartMoneyWalletAPIResponse(success=False, errorMessage=str(e))
    
    def fetchPolymarketCategories(self, categories: List[str], timePeriod: str = TIME_PERIOD_MONTH) -> FetchSmartMoneyWalletAPIResponse:
        return self.fetchAndPersist(platform=PLATFORM_POLYMARKET, categories=categories, timePeriod=timePeriod)
    
    def fetchAllPolymarketCategories(self, timePeriod: str = TIME_PERIOD_MONTH) -> FetchSmartMoneyWalletAPIResponse:
        return self.fetchAndPersist(platform=PLATFORM_POLYMARKET, categories=SMART_MONEY_CATEGORIES, timePeriod=timePeriod)
