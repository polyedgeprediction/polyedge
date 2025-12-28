"""
Scheduler for orchestrating the complete trade processing workflow.
Main entry point that coordinates all trade processing operations.
"""
from gzip import READ
import logging

from positions.schedulers.RecentlyClosedPositionsScheduler import RecentlyClosedPositionsScheduler
from trades.handlers.TradePersistenceHandler import TradePersistenceHandler
from trades.services.TradeProcessingService import TradeProcessingService
from positions.enums.TradeStatus import TradeStatus

logger = logging.getLogger(__name__)


class FetchTradesScheduler:
    
    @staticmethod
    def fetchTrades() -> None:
        
        try:
            logger.info("FETCH_TRADES_SCHEDULER :: Started")
            walletsWithMarkets = TradePersistenceHandler.getWalletsWithMarketsNeedingTradeSync(TradeStatus.NEED_TO_PULL_TRADES)
            
            if not walletsWithMarkets:
                logger.info("FETCH_TRADES_SCHEDULER :: No wallets with markets needing trade sync")
            else:
                TradeProcessingService.syncTradeForWallets(walletsWithMarkets,TradeStatus.NEED_TO_PULL_TRADES, TradeStatus.TRADES_SYNCED)
                
            TradePersistenceHandler.bulkUpdatePNL(TradeStatus.NEED_TO_CALCULATE_PNL, TradeStatus.TRADES_SYNCED)
            FetchTradesScheduler.updateRecentlyClosedPositionsWithPNLData()

            logger.info("FETCH_TRADES_SCHEDULER :: Completed")
        except Exception as e:
            logger.error(f"FETCH_TRADES_SCHEDULER :: Critical error: {e}")
            return

    @staticmethod
    def updateRecentlyClosedPositionsWithPNLData():
        try:
            logger.info("FETCH_TRADES_SCHEDULER :: Started updating recently closed positions")
            RecentlyClosedPositionsScheduler.updatePNLDataForRecentlyClosedPositions()
            logger.info("FETCH_TRADES_SCHEDULER :: Completed updating recently closed positions")
        except Exception as e:
            logger.error(f"FETCH_TRADES_SCHEDULER :: Critical error: {e}")

