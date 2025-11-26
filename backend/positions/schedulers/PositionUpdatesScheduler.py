"""
Position Updates Scheduler for updating existing wallet positions.
Runs every 30 minutes to update positions for OLD wallets.
"""
import logging
from typing import List, Dict
from django.db import transaction

from wallets.models import Wallet
from wallets.enums import WalletType
from positions.implementations.polymarket.OpenPositionAPI import OpenPositionAPI
from positions.handlers.PositionPersistenceHandler import PositionPersistenceHandler
from positions.pojos.PositionUpdateStats import SchedulerExecutionStats, WalletUpdateStats

logger = logging.getLogger(__name__)


class PositionUpdatesScheduler:

    def __init__(self):
        self.openPositionAPI = OpenPositionAPI()

    @staticmethod
    def execute() -> SchedulerExecutionStats:
        logger.info("POSITION_UPDATES_SCHEDULER :: Started")
        
        # Get all OLD wallets (wallets that have been processed before)
        oldWallets = PositionUpdatesScheduler._getWalletsToProcess()
        
        if not oldWallets:
            logger.info("POSITION_UPDATES_SCHEDULER :: No OLD wallets found")
            return SchedulerExecutionStats(success=True, message='No OLD wallets to process')
        
        scheduler = PositionUpdatesScheduler()
        executionStats = SchedulerExecutionStats()
        
        # Process each wallet
        for wallet in oldWallets:
            try:
                walletUpdateStats = scheduler._processWalletUpdates(wallet)
                executionStats.addWalletStats(walletUpdateStats)
                
                logger.info(
                    "POSITION_UPDATES_SCHEDULER :: Processed wallet | Wallet: %s | Updated: %d | Closed: %d | Reopened: %d",
                    wallet.proxywallet[:10],
                    walletUpdateStats.updated,
                    walletUpdateStats.markedClosed,
                    walletUpdateStats.reopened
                )
                
            except Exception as e:
                # Create failed wallet stats
                failedStats = WalletUpdateStats(
                    walletId=wallet.walletsid,
                    walletAddress=wallet.proxywallet,
                    success=False,
                    errorMessage=str(e)
                )
                executionStats.addWalletStats(failedStats)
                
                logger.info(
                    "POSITION_UPDATES_SCHEDULER :: Failed to process wallet | Wallet: %s | Error: %s",
                    wallet.proxywallet[:10],
                    str(e),
                    exc_info=True
                )
        
        # Log final statistics
        logger.info(
            "POSITION_UPDATES_SCHEDULER :: Completed | "
            "Processed: %d | Succeeded: %d | Failed: %d | "
            "Total Updated: %d | Total Closed: %d | Total Reopened: %d | Total Created: %d",
            executionStats.walletsProcessed,
            executionStats.walletsSucceeded, 
            executionStats.walletsFailed,
            executionStats.totalUpdated,
            executionStats.totalMarkedClosed,
            executionStats.totalReopened,
            executionStats.totalCreated
        )
        
        return executionStats

    def _processWalletUpdates(self, wallet: Wallet) -> WalletUpdateStats:
        try:
            # Fetch open positions from API once
            apiOpenPositions = self.openPositionAPI.fetchOpenPositions(wallet.proxywallet)
            
            # Process all three update cases with single DB operation
            with transaction.atomic():
                result = PositionPersistenceHandler.updatePositionsForWallet(
                    wallet.walletsid, 
                    apiOpenPositions
                )
                
                # Update wallet's last updated timestamp
                wallet.save(update_fields=['lastupdatedat'])
                
            # Convert result to wallet stats
            return result.toWalletStats(wallet.walletsid, wallet.proxywallet)
            
        except Exception as e:
            logger.info(
                "POSITION_UPDATES_SCHEDULER :: Failed to process wallet updates | Wallet: %s | Error: %s",
                wallet.proxywallet[:10],
                str(e),
                exc_info=True
            )
            raise

    @staticmethod
    def _getWalletsToProcess() -> List[Wallet]:
        """
        Get list of wallets that need position updates.
        
        Returns:
            List of OLD wallets ordered by last update time
        """
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