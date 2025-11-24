from typing import List
import logging

from wallets.pojos.FetchSmartMoneyWalletRequest import FetchSmartMoneyWalletRequest
from wallets.pojos.FetchSmartMoneyWalletResponse import FetchSmartMoneyWalletResponse
from wallets.Constants import TIME_PERIOD_MONTH, ORDER_BY_PNL
from wallets.PlatformRegistry import PlatformRegistry

logger = logging.getLogger(__name__)


class FetchSmartMoneyWalletAction:
    
    def fetchWallets(self, platform: str, categories: List[str], timePeriod: str = TIME_PERIOD_MONTH, orderBy: str = ORDER_BY_PNL, maxRecords: int = None) -> FetchSmartMoneyWalletResponse:
        try:
            request = FetchSmartMoneyWalletRequest(platform=platform, categories=categories, timePeriod=timePeriod, orderBy=orderBy, maxRecords=maxRecords)
            platformEnum = PlatformRegistry.fromString(platform)
            translator = platformEnum.getTranslator()
            return translator.fetchSmartMoneyWallets(request)
        
            
        except Exception as e:
            logger.error("FETCH_WALLETS_API :: ACTION :: Error fetching wallets | Platform: %s | Error: %s", platform, str(e), exc_info=True)
            return FetchSmartMoneyWalletResponse(success=False, categories=categories, timePeriod=timePeriod, platform=platform, errorMessage=str(e))
