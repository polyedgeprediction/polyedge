"""
Position Updates Scheduler for updating existing wallet positions.
Runs every 30 minutes to update positions for OLD wallets.
Production-grade scheduler with parallel processing for efficient updates.
"""
import logging
from typing import List
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.db import transaction, connection

from wallets.models import Wallet
from wallets.enums import WalletType
from wallets.Constants import PARALLEL_POSITION_UPDATE_WORKERS
from positions.implementations.polymarket.OpenPositionAPI import OpenPositionAPI
from positions.handlers.PositionPersistenceHandler import PositionPersistenceHandler
from positions.pojos.PositionUpdateStats import SchedulerExecutionStats, WalletUpdateStats
from positions.schedulers.PositionCurrentValueUpdater import PositionCurrentValueUpdater
from trades.schedulers.BatchSyncScheduler import BatchSyncScheduler

logger = logging.getLogger(__name__)


class PositionUpdatesScheduler:

    def __init__(self):
        self.openPositionAPI = OpenPositionAPI()

    @staticmethod
    def updatePositions() -> SchedulerExecutionStats:
        startTime = datetime.now(timezone.utc)

        # Get all OLD wallets (wallets that have been processed before)
        oldWallets = PositionUpdatesScheduler.getAllOldWallets()

        if not oldWallets:
            logger.info("POSITION_UPDATES_SCHEDULER :: No OLD wallets to process")
            return SchedulerExecutionStats(success=True, message='No OLD wallets to process')

        logger.info("POSITION_UPDATES_SCHEDULER :: Started | Wallets: %d | Workers: %d", len(oldWallets), PARALLEL_POSITION_UPDATE_WORKERS)

        # Initialize scheduler and stats
        scheduler = PositionUpdatesScheduler()
        executionStats = SchedulerExecutionStats()

        # Process wallets in parallel
        scheduler.processWalletsInParallel(oldWallets, executionStats)

        # Calculate duration and log final statistics
        duration = (datetime.now(timezone.utc) - startTime).total_seconds()
        logger.info("POSITION_UPDATES_SCHEDULER :: Completed | %.2fs | Success: %d | Failed: %d",duration,executionStats.walletsSucceeded,executionStats.walletsFailed)

        # Update calculated current values for all positions in markets with open positions
        # When we update the positions, we only update the amount remaining, so we need to update the calculated current value[which is market wise]
        PositionCurrentValueUpdater.updateCalculatedCurrentValues()

        # Sync missing batch records
        BatchSyncScheduler.addMissingInitialBatchRecords()

        return executionStats

    def processWalletsInParallel(self, wallets: List[Wallet], executionStats: SchedulerExecutionStats) -> None:
        with ThreadPoolExecutor(max_workers=PARALLEL_POSITION_UPDATE_WORKERS) as executor:
            futures = {
                executor.submit(self.processSingleWallet, wallet, executionStats): wallet
                for wallet in wallets
            }

            for future in as_completed(futures):
                wallet = futures[future]
                try:
                    # Result already handled in processSingleWallet
                    future.result()
                except Exception as e:
                    # Unexpected error not caught in processSingleWallet
                    logger.info("POSITION_UPDATES_SCHEDULER :: Unexpected error | %s | %s",wallet.proxywallet[:10],str(e))

    def processSingleWallet(self, wallet: Wallet, executionStats: SchedulerExecutionStats) -> None:
        try:
            # Process wallet position updates
            walletUpdateStats = self.processWalletPositionUpdates(wallet)

            # Add stats (thread-safe)
            executionStats.addWalletStats(walletUpdateStats)

            # Log success if there were changes
            if walletUpdateStats.hasChanges():
                logger.info("POSITION_UPDATES_SCHEDULER :: SUCCESS | %s | Changes: %d",wallet.proxywallet[:10],walletUpdateStats.getTotalChanges())

        except Exception as e:
            # Create failed wallet stats
            failedStats = WalletUpdateStats(walletId=wallet.walletsid,walletAddress=wallet.proxywallet,success=False,errorMessage=str(e))

            # Add failed stats (thread-safe)
            executionStats.addWalletStats(failedStats)

            # Log failure
            logger.info("POSITION_UPDATES_SCHEDULER :: FAILED | %s | %s",wallet.proxywallet[:10],str(e))

        finally:
            # Close database connection for this thread to prevent connection exhaustion
            connection.close()

    def processWalletPositionUpdates(self, wallet: Wallet) -> WalletUpdateStats:
        # Fetch open positions from API
        apiOpenPositions = self.openPositionAPI.fetchOpenPositions(wallet.proxywallet)

        # Update positions in database
        result = PositionPersistenceHandler.updatePositionsForWallet(wallet,apiOpenPositions)

        # Convert result to wallet stats
        return result.toWalletStats(wallet.walletsid, wallet.proxywallet)

    @staticmethod
    def getAllOldWallets() -> List[Wallet]:
        return list(Wallet.objects.filter(
            wallettype=WalletType.OLD,
            isactive=1
        ).order_by('lastupdatedat'))

    @staticmethod
    def getExecutionSummary(executionStats: SchedulerExecutionStats) -> str:
        """
        Generate human-readable execution summary.
        
        Args:
            executionStats: SchedulerExecutionStats from execute()
            
        Returns:
            Formatted summary string
        """
        return executionStats.getSummary()