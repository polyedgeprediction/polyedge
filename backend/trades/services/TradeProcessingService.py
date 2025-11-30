"""
Polymarket trade processing service with real-time aggregation.
Clean pipeline: API → Parse → Aggregate → Persist
"""
from typing import List, Optional
import logging

from wallets.pojos.WalletWithMarkets import WalletWithMarkets
from markets.pojos.Market import Market
from trades.pojos.AggregatedTrade import AggregatedTrade
from trades.pojos.DailyTrades import DailyTrades
from trades.implementation.PolymarketUserActivityResponse import PolyMarketUserActivityResponse
from trades.implementation.PolymarketAPIService import PolymarketAPIService
from trades.handlers.TradePersistenceHandler import TradePersistenceHandler
from positions.enums.TradeStatus import TradeStatus

logger = logging.getLogger(__name__)


class TradeProcessingService:
    """
    Polymarket trade processing service with real-time aggregation.
    
    Processes wallet trades through a clean pipeline:
    API → Parse → Aggregate → Persist
    """
    
    @staticmethod
    def syncTradeForWallets(wallets: List[WalletWithMarkets], finalStatus: TradeStatus, fallbackStatus: TradeStatus) -> None:
        """Process trades for all wallets with bulk persistence at the end."""
        for wallet in wallets:
            try:
                TradeProcessingService.syncTradeForWallet(wallet, finalStatus, fallbackStatus)
            except Exception as e:
                logger.info(f"FETCH_TRADES_SCHEDULER :: Failed to process wallet {wallet.walletId}: {e}")
        
        # Single bulk persistence call for all wallets
        TradeProcessingService.persistAggregatedTrades(wallets,finalStatus)
    
    @staticmethod
    def syncTradeForWallet(wallet: WalletWithMarkets, finalStatus: TradeStatus, fallbackStatus: TradeStatus) -> None:
        """Process all markets for a single wallet."""
        for market in wallet.markets.values():
            try:
                TradeProcessingService.syncTradeForMarket(wallet, market, finalStatus, fallbackStatus)
            except Exception as e:
                logger.info(f"FETCH_TRADES_SCHEDULER :: Failed to process market {market.conditionId} for wallet {wallet.walletId}: {e}")
                market.markTradeStatus(fallbackStatus)
    
    @staticmethod
    def syncTradeForMarket(wallet: WalletWithMarkets, market: Market, finalStatus: TradeStatus, fallbackStatus: TradeStatus) -> None:
        """Process trades for a single market with real-time aggregation."""
        # Step 1: Fetch trades from API with latest timestamp
        tradesFromAPI, latestTimestamp = TradeProcessingService.fetchTrades(wallet, market)
        
        # Step 2: Check for API errors before processing

        if PolyMarketUserActivityResponse.hasApiErrors(tradesFromAPI):
            errorCode, errorMessage = PolyMarketUserActivityResponse.getFirstError(tradesFromAPI)
            logger.info(f"FETCH_TRADES_SCHEDULER :: API errors for market {market.conditionId}: {errorCode} - {errorMessage}")
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
        
        logger.info(f"Processed market {market.conditionId}: {len(tradesFromAPI)} transactions")
    
    @staticmethod
    def fetchTrades(wallet: WalletWithMarkets, market: Market) -> tuple[List[PolyMarketUserActivityResponse], Optional[int]]:
        """Fetch trades from Polymarket API based on sync requirements."""
        if market.needsTradeSync():
            return PolymarketAPIService.fetchAllTrades(wallet.proxyWallet, market.conditionId)
        else:
            startTimestamp = market.batch.getLastFetchedTimestamp() if market.batch else None
            return PolymarketAPIService.fetchTradesInRange(
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
            from django.db import transaction
            
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
                calculatedPnl = 0
                
                # Step 1: Bulk persist trades - most critical operation first
                if aggregatedTrades:
                    persistedTrades = TradePersistenceHandler.bulkPersistAggregatedTrades(aggregatedTrades)
                
                # Step 2: Update positions and batches in single operation
                if statusUpdates or batchUpdates:
                    updatedStatuses, updatedBatches = TradePersistenceHandler.bulkUpdateStatusAndTimestamps(statusUpdates, batchUpdates)
                
                # Step 3: Calculate PNL for positions marked for calculation
                calculatedPnl = TradePersistenceHandler.bulkUpdatePNL(
                    TradeStatus.NEED_TO_CALCULATE_PNL,
                    finalStatus
                )
                
                logger.info(
                    f"FETCH_TRADES_SCHEDULER :: Complete pipeline executed | "
                    f"Trades: {persistedTrades}, Positions: {updatedStatuses}, "
                    f"Batches: {updatedBatches}, PNL: {calculatedPnl}"
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