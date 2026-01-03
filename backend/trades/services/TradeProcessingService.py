"""
Polymarket trade processing service with real-time aggregation.
Clean pipeline: API → Parse → Aggregate → Persist
Parallel processing for efficient wallet-level trade fetching.
"""
from typing import List, Optional
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.db import connection

from wallets.pojos.WalletWithMarkets import WalletWithMarkets
from wallets.Constants import PARALLEL_TRADE_WORKERS
from markets.pojos.Market import Market
from trades.pojos.AggregatedTrade import AggregatedTrade
from trades.pojos.DailyTrades import DailyTrades
from trades.implementation.PolymarketUserActivityResponse import PolyMarketUserActivityResponse
from trades.implementation.PolymarketAPIService import PolymarketAPIService
from trades.handlers.TradePersistenceHandler import TradePersistenceHandler
from positions.enums.TradeStatus import TradeStatus
from django.db import transaction

logger = logging.getLogger(__name__)


class TradeProcessingService:
    """
    Polymarket trade processing service with real-time aggregation.

    Processes wallet trades through a clean pipeline:
    API → Parse → Aggregate → Persist
    """

    def __init__(self):
        """Initialize with PolymarketAPIService instance."""
        self.apiService = PolymarketAPIService()

    @staticmethod
    def syncTradeForWallets(wallets: List[WalletWithMarkets], fallbackStatus: TradeStatus, finalStatus: TradeStatus) -> None:
        if not wallets:
            logger.info("FETCH_TRADES_SCHEDULER :: No wallets to process")
            return

        logger.info("FETCH_TRADES_SCHEDULER :: Started parallel processing | Wallets: %d | Workers: %d",len(wallets),PARALLEL_TRADE_WORKERS)

        # Process wallets in parallel
        walletsSucceeded, walletsFailed = TradeProcessingService.processWalletsInParallel(wallets, fallbackStatus, finalStatus)

        logger.info("FETCH_TRADES_SCHEDULER :: Parallel processing completed | Success: %d | Failed: %d",walletsSucceeded,walletsFailed)

        # Single bulk persistence call for all wallets
        TradeProcessingService.persistAggregatedTrades(wallets, finalStatus)

    @staticmethod
    def processWalletsInParallel(wallets: List[WalletWithMarkets], fallbackStatus: TradeStatus, finalStatus: TradeStatus) -> tuple:
        walletsSucceeded = 0
        walletsFailed = 0
        statsLock = threading.Lock()

        with ThreadPoolExecutor(max_workers=PARALLEL_TRADE_WORKERS) as executor:
            # Submit all wallet processing tasks
            futures = {
                executor.submit(
                    TradeProcessingService.processSingleWallet,
                    wallet,
                    fallbackStatus,
                    finalStatus
                ): wallet
                for wallet in wallets
            }

            # Process completed tasks as they finish
            for future in as_completed(futures):
                wallet = futures[future]
                try:
                    success = future.result()

                    with statsLock:
                        if success:
                            walletsSucceeded += 1
                        else:
                            walletsFailed += 1

                except Exception as e:
                    with statsLock:
                        walletsFailed += 1
                    logger.error(
                        "FETCH_TRADES_SCHEDULER :: Unexpected error | Wallet: %d | Error: %s",
                        wallet.walletId,
                        str(e),
                        exc_info=True
                    )

        return walletsSucceeded, walletsFailed

    @staticmethod
    def processSingleWallet(wallet: WalletWithMarkets, fallbackStatus: TradeStatus, finalStatus: TradeStatus) -> bool:
        try:
            # Create service instance for this thread
            service = TradeProcessingService()

            # Process all markets for this wallet
            service.syncTradeForWallet(wallet, fallbackStatus, finalStatus)

            logger.info("FETCH_TRADES_SCHEDULER :: Wallet processed | Wallet: %d | Markets: %d",wallet.walletId,len(wallet.markets))

            return True

        except Exception as e:
            logger.info("FETCH_TRADES_SCHEDULER :: Failed to process wallet | Wallet: %d | Error: %s",wallet.walletId,str(e),exc_info=True)
            return False

        finally:
            # Close database connection for this thread to prevent connection exhaustion
            connection.close()


    def syncTradeForWallet(self, wallet: WalletWithMarkets, fallbackStatus: TradeStatus, finalStatus: TradeStatus) -> None:
        for market in wallet.markets.values():
            try:
                self.syncTradeForMarket(wallet, market, fallbackStatus, finalStatus)
            except Exception as e:
                logger.info(f"FETCH_TRADES_SCHEDULER :: Failed to process market {market.marketSlug} for wallet {wallet.walletId}: {e}")
                market.markTradeStatus(fallbackStatus)

    def syncTradeForMarket(self, wallet: WalletWithMarkets, market: Market, fallbackStatus: TradeStatus, finalStatus: TradeStatus) -> None:
        # Step 1: Fetch trades from API with latest timestamp
        tradesFromAPI, latestTimestamp = self.fetchTrades(wallet, market)

        # Step 2: Check for API errors before processing

        if PolyMarketUserActivityResponse.hasApiErrors(tradesFromAPI):
            errorCode, errorMessage = PolyMarketUserActivityResponse.getFirstError(tradesFromAPI)
            logger.info(f"FETCH_TRADES_SCHEDULER :: API errors for market {market.marketSlug}: {errorCode} - {errorMessage}")
            market.markTradeStatus(fallbackStatus)
            return

        if not tradesFromAPI:
            market.markTradeStatus(finalStatus)
            return

        # Step 3: Process trades with real-time aggregation
        TradeProcessingService.aggregateTrades(wallet, market, tradesFromAPI)

        # Step 4: Prepare for bulk persistence
        TradeProcessingService.updateAggregatedTradeData(wallet, market, latestTimestamp)

        # Step 5: Mark for PNL calculation
        market.markTradeStatus(TradeStatus.NEED_TO_CALCULATE_PNL)

        logger.info(f"Processed market {market.marketSlug}: {len(tradesFromAPI)} transactions")

    def fetchTrades(self, wallet: WalletWithMarkets, market: Market) -> tuple[List[PolyMarketUserActivityResponse], Optional[int]]:
        if market.needsTradeSync():
            return self.apiService.fetchAllTrades(wallet.proxyWallet, market.conditionId)
        else:
            startTimestamp = market.batch.getLastFetchedTimestamp() if market.batch else None
            return self.apiService.fetchTradesInRange(
                wallet.proxyWallet,
                market.conditionId,
                startTimestamp,
                PolymarketAPIService.getCurrentTimestamp()
            )
    
    @staticmethod
    def aggregateTrades(wallet: WalletWithMarkets, market: Market, trades: List[PolyMarketUserActivityResponse]) -> None:
        """Process trades with real-time aggregation directly into market's daily trades."""
        for trade in trades:
            tradeDate = trade.transactionDate
            
            # Get existing DailyTrades from market or create new one
            dailyTrades = market.getDailyTrades(tradeDate)
            if dailyTrades is None:
                dailyTrades = DailyTrades(
                    marketId=market.conditionId,
                    walletId=wallet.walletId,
                    tradeDate=tradeDate,
                    marketPk=market.marketPk  # Include database primary key
                )
                market.addDailyTrades(dailyTrades)
            
            dailyTrades.processPolymarketTransaction(trade)
    
    @staticmethod
    def updateAggregatedTradeData(wallet: WalletWithMarkets, market: Market, latestTimestamp: Optional[int]) -> None:
        """Prepare aggregated trades and timestamps for bulk persistence."""
        # Collect all aggregated trades (already in persistence format!)
        allTrades = []
        for dailyTrades in market.dailyTrades.values():
            allTrades.extend(dailyTrades.getAllTrades())
        
        # Add directly to persistence (no conversion needed!)
        if allTrades:
            market.addTradesToPersist(allTrades)
        
        # Mark batch timestamp for bulk update using efficiently tracked timestamp
        if market.batch and latestTimestamp:
            market.markBatchTimestamp(latestTimestamp)
    
    
    @staticmethod
    def persistAggregatedTrades(wallets: List[WalletWithMarkets], finalStatus: TradeStatus) -> None:
        try:
            # Collect all persistence data in one pass
            aggregatedTrades, statusUpdates, batchUpdates = TradeProcessingService.collectAggregatedData(wallets)
            
            # Early exit if no data to persist
            if not aggregatedTrades and not statusUpdates and not batchUpdates:
                logger.info("FETCH_TRADES_SCHEDULER :: No data to persist")
                return
            
            # Execute all operations in a single atomic transaction for maximum efficiency
            with transaction.atomic():
                persistedTrades = 0
                updatedStatuses = 0
                updatedBatches = 0
                
                # Step 1: Bulk persist trades - most critical operation first
                if aggregatedTrades:
                    persistedTrades = TradePersistenceHandler.bulkPersistAggregatedTrades(aggregatedTrades)
                
                # Step 2: Update positions and batches in single operation
                if statusUpdates or batchUpdates:
                    updatedStatuses, updatedBatches = TradePersistenceHandler.bulkUpdateStatusAndTimestamps(statusUpdates, batchUpdates)
                
                logger.info(
                    f"FETCH_TRADES_SCHEDULER :: Complete pipeline executed | "
                    f"Trades: {persistedTrades}, Positions: {updatedStatuses}, "
                    f"Batches: {updatedBatches}"
                )
                
        except Exception as e: 
            logger.error(f"FETCH_TRADES_SCHEDULER :: Critical error during bulk persistence: {e}")
            raise
    
    @staticmethod
    def collectAggregatedData(wallets: List[WalletWithMarkets]) -> tuple:
        """Collect all data that needs to be persisted."""
        trades = []
        statusUpdates = []
        batchUpdates = []
        
        for wallet in wallets:
            for market in wallet.markets.values():
                if market.tradesToPersist:
                    for trade in market.tradesToPersist:
                        trades.append({
                            'trade': trade,
                            'walletId': wallet.walletId,
                            'marketPk': market.marketPk  # Direct market primary key - no lookup needed!
                        })
                    
                if market.newTradeStatus:
                    statusUpdates.append({
                        'walletId': wallet.walletId,
                        'conditionId': market.conditionId,
                        'status': market.newTradeStatus
                    })
                    
                if market.newBatchTimestamp and market.batch:
                    batchUpdates.append({
                        'batchId': market.batch.batchId,
                        'timestamp': market.newBatchTimestamp
                    })
        
        return trades, statusUpdates, batchUpdates