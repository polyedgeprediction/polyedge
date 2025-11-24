import requests
import time
import logging
from typing import List, Dict
from datetime import datetime

from wallets.Translator import ProcessorTranslator
from wallets.pojos.FetchSmartMoneyWalletRequest import FetchSmartMoneyWalletRequest
from wallets.pojos.FetchSmartMoneyWalletResponse import FetchSmartMoneyWalletResponse
from wallets.pojos.Wallet import Wallet
from wallets.implementations.polymarket.Constants import (
    POLYMARKET_API_BASE_URL,
    POLYMARKET_LEADERBOARD_ENDPOINT,
    POLYMARKET_HEADERS,
    MAX_RETRY_ATTEMPTS,
    RETRY_BACKOFF_SECONDS
)
from wallets.implementations.polymarket.PolymarketSmartMoneyParser import PolymarketSmartMoneyParser

logger = logging.getLogger(__name__)


class PolymarketTranslator(ProcessorTranslator):
    
    def __init__(self):
        self.baseUrl = POLYMARKET_API_BASE_URL
        self.endpoint = POLYMARKET_LEADERBOARD_ENDPOINT
        self.headers = POLYMARKET_HEADERS.copy()
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.parser = PolymarketSmartMoneyParser()
    
    def fetchSmartMoneyWallets(self, request: FetchSmartMoneyWalletRequest) -> FetchSmartMoneyWalletResponse:
        fetchTimestamp = datetime.now()
        walletMap: Dict[str, Wallet] = {}
        
        try:
            for category in request.categories:
                logger.info("FETCH_WALLETS_API :: TRANSLATOR :: Fetching category: %s", category)
                self.fetchCategoryPNL(category, request.timePeriod, request.orderBy, request.limit, request.maxRecords, request.platform, walletMap)
                logger.info("FETCH_WALLETS_API :: TRANSLATOR :: Category %s completed | Total unique wallets so far: %d", 
                           category, len(walletMap))
            
            totalWallets = len(walletMap)
            logger.info("FETCH_WALLETS_API :: TRANSLATOR :: All categories fetched successfully | Total unique wallets: %d | Categories: %s", 
                       totalWallets, request.categories)
            
            return FetchSmartMoneyWalletResponse(
                success=True,
                wallets=list(walletMap.values()),
                categories=request.categories,
                timePeriod=request.timePeriod,
                platform=request.platform,
                fetchTimestamp=fetchTimestamp
            )
            
        except Exception as e:
            logger.error("FETCH_WALLETS_API :: TRANSLATOR :: Error fetching wallets | Categories: %s | Error: %s", 
                        request.categories, str(e), exc_info=True)
            return FetchSmartMoneyWalletResponse(
                success=False,
                categories=request.categories,
                timePeriod=request.timePeriod,
                platform=request.platform,
                errorMessage=str(e),
                fetchTimestamp=fetchTimestamp
            )
    
    def fetchCategoryPNL(self, category: str, timePeriod: str, orderBy: str, limit: int, maxRecords: int, platform: str, walletMap: Dict[str, Wallet]) -> None:
        currentOffset = 0
        minPnlThreshold = 10000
        
        while True:
            batchData = self.hitAPI(category, timePeriod, orderBy, limit, currentOffset)
            
            if not batchData:
                logger.info("FETCH_WALLETS_API :: TRANSLATOR :: No more data for category: %s", category)
                break
            
            foundLowPnl = self.parser.parseAndUpdateWallets(batchData, category, timePeriod, platform, walletMap, minPnlThreshold)
            
            if foundLowPnl:
                logger.info("FETCH_WALLETS_API :: TRANSLATOR :: PNL threshold reached | Category: %s | Offset: %d | MinPNL: %d | Stopping pagination", 
                           category, currentOffset, minPnlThreshold)
                break
            
            currentOffset += limit
            
            if len(batchData) < limit:
                logger.info("FETCH_WALLETS_API :: TRANSLATOR :: Last batch (incomplete) | Category: %s | Records: %d", category, len(batchData))
                break
    
    def hitAPI(self, category: str, timePeriod: str, orderBy: str, limit: int, offset: int) -> List[dict]:
        url = f"{self.baseUrl}{self.endpoint}"
        params = {"timePeriod": timePeriod, "orderBy": orderBy, "limit": limit, "offset": offset, "category": category}
        
        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            try:
                logger.debug("FETCH_WALLETS_API :: TRANSLATOR :: API call attempt %d | Category: %s | Offset: %d", 
                            attempt, category, offset)
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                logger.debug("FETCH_WALLETS_API :: TRANSLATOR :: API call successful | Category: %s | Records: %d", 
                            category, len(data) if isinstance(data, list) else 0)
                return data
            except requests.exceptions.RequestException as e:
                if attempt == MAX_RETRY_ATTEMPTS:
                    logger.error("FETCH_WALLETS_API :: TRANSLATOR :: All retry attempts exhausted | Category: %s | Error: %s", 
                                category, str(e), exc_info=True)
                    raise
                sleepTime = RETRY_BACKOFF_SECONDS * attempt
                logger.warning("FETCH_WALLETS_API :: TRANSLATOR :: Retry %d/%d in %ds | Category: %s | Error: %s", 
                              attempt, MAX_RETRY_ATTEMPTS, sleepTime, category, str(e))
                time.sleep(sleepTime)
        
        return []
