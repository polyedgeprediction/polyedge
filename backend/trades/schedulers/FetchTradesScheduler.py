"""
Scheduler for orchestrating the complete trade processing workflow.
Main entry point that coordinates all trade processing operations.
"""
import logging

from trades.handlers.TradePersistenceHandler import TradePersistenceHandler
from trades.services.TradeProcessingService import TradeProcessingService
from positions.enums.TradeStatus import TradeStatus

logger = logging.getLogger(__name__)


class TradeProcessingScheduler:
    
    @staticmethod
    def fetchTrades() -> None:
        
        try:
            logger.info("FETCH_TRADES_SCHEDULER :: Started")
            walletsWithMarkets = TradePersistenceHandler.getWalletsWithMarketsNeedingTradeSync()
            
            if not walletsWithMarkets:
                logger.info("FETCH_TRADES_SCHEDULER :: No wallets with markets needing trade sync")
                return
            
            TradeProcessingService.syncTradeForWallets(walletsWithMarkets, TradeStatus.NEED_TO_PULL_TRADES, TradeStatus.TRADES_SYNCED)

            logger.info("FETCH_TRADES_SCHEDULER :: Completed")
            
        except Exception as e:
            logger.error(f"FETCH_TRADES_SCHEDULER :: Critical error: {e}")
            return


