"""
Wallet PnL Scheduler - Orchestrates periodic PnL calculations for all wallets.
Production-grade scheduler with optimized bulk data loading and parallel processing.
"""
import logging
from typing import List, Optional
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.db import transaction, connection

from wallets.models import Wallet, WalletPnl
from wallets.schedulers.PnlCalculationService import PnlCalculationService, PnlCalculationResult
from wallets.schedulers.PnlSchedulerMetrics import PnlSchedulerMetrics
from wallets.schedulers.BulkDataLoader import BulkDataLoader
from wallets.Constants import PARALLEL_PNL_SCHEDULER_WORKERS

logger = logging.getLogger(__name__)


class WalletPnlScheduler:

    DEFAULT_PERIODS = [30, 60, 90]

    def __init__(self):
        self.calculationService = PnlCalculationService()
        self.dataLoader = BulkDataLoader()

    def runScheduler(self, periodDays: Optional[List[int]] = None, walletIds: Optional[List[int]] = None) -> dict: 
        periods = periodDays or self.DEFAULT_PERIODS
        startTime = datetime.now(timezone.utc)

        logger.info("PNL_SCHEDULER :: Starting | Periods: %s | Workers: %d", periods, PARALLEL_PNL_SCHEDULER_WORKERS)

        # Load wallets
        wallets = self.loadWallets(walletIds)
        if not wallets:
            logger.info("PNL_SCHEDULER :: No wallets to process")
            return self.buildEmptyResult(startTime)

        totalCalculations = len(wallets) * len(periods)
        logger.info("PNL_SCHEDULER :: Wallets: %d | Calculations: %d",len(wallets), totalCalculations)

        # Bulk load all data (1 query) - returns EventHierarchy with trade ranges in markets
        eventHierarchyByWallet = self.dataLoader.loadDataForWallets(wallets, periods)

        # Initialize metrics
        metrics = PnlSchedulerMetrics.create(totalWallets=len(wallets),totalCalculations=totalCalculations)

        # Process in parallel
        self.processWalletsInParallel(wallets, periods, eventHierarchyByWallet, metrics, startTime)

        # Build result
        duration = (datetime.now(timezone.utc) - startTime).total_seconds()
        result = self.buildResult(metrics, duration, startTime)

        logger.info("PNL_SCHEDULER :: Complete | Succeeded: %d | Failed: %d | Duration: %.2fs",result['succeeded'], result['failed'], duration)

        return result


    def loadWallets(self, walletIds: Optional[List[int]]) -> List[Wallet]:
        """Load wallets to process."""
        query = Wallet.objects.filter(isactive=1)

        if walletIds:
            query = query.filter(walletsid__in=walletIds)

        return list(query)

    def processWalletsInParallel(self, wallets: List[Wallet], periods: List[int],eventHierarchyByWallet: dict,metrics: PnlSchedulerMetrics, startTime: datetime) -> None:

        logger.info("PNL_SCHEDULER :: Processing %d wallets × %d periods with %d workers",len(wallets), len(periods), PARALLEL_PNL_SCHEDULER_WORKERS)

        tasks = [(wallet, period) for wallet in wallets for period in periods]

        with ThreadPoolExecutor(max_workers=PARALLEL_PNL_SCHEDULER_WORKERS) as executor:
            futures = {
                executor.submit(self.processSingleTask, wallet, period,eventHierarchyByWallet, metrics, startTime): (wallet, period)
                for wallet, period in tasks
            }

            for future in as_completed(futures):
                wallet, period = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.info("PNL_SCHEDULER :: Unexpected error | Wallet: %s | Period: %d | Error: %s",wallet.proxywallet[:10], period, str(e))
                    metrics.recordCalculationFailure(wallet.walletsid, period, str(e))

        logger.info("PNL_SCHEDULER :: Batch complete | Succeeded: %d | Failed: %d",metrics.succeededCalculations, metrics.failedCalculations)

    def processSingleTask(self, wallet: Wallet, periodDays: int,eventHierarchyByWallet: dict,metrics: PnlSchedulerMetrics, startTime: datetime) -> None:
        try:
            # Get pre-loaded data (O(1) dictionary lookup, no DB queries)
            # EventHierarchy contains trade date ranges in Market POJOs
            eventHierarchy = eventHierarchyByWallet.get(wallet.walletsid, {})

            # Calculate PnL using pre-loaded EventHierarchy (markets have trade ranges)
            result = self.calculationService.calculatePnlFromBulkData(wallet, periodDays, eventHierarchy, startTime)

            # Persist to database
            self.persistPnlData(wallet, periodDays, result)

            # Record success
            metrics.recordCalculationSuccess(periodDays)

            # Log success with PnL values
            self.logSuccess(wallet, periodDays, result)

        except Exception as e:
            metrics.recordCalculationFailure(wallet.walletsid, periodDays, str(e))
            logger.info("PNL_SCHEDULER :: Failed | Wallet: %s | Period: %d | Error: %s",wallet.proxywallet[:10], periodDays, str(e), exc_info=True)
        finally:
            # Close database connection for this thread to prevent connection exhaustion
            connection.close()

    @transaction.atomic
    def persistPnlData(self, wallet: Wallet, periodDays: int,result: PnlCalculationResult) -> None:
        WalletPnl.objects.update_or_create(
            wallet=wallet,
            period=periodDays,
            defaults={
                'start': result.startTime,
                'end': result.endTime,
                'openamountinvested': result.openAmountInvested,
                'openamountout': result.openAmountOut,
                'opencurrentvalue': result.openCurrentValue,
                'closedamountinvested': result.closedAmountInvested,
                'closedamountout': result.closedAmountOut,
                'closedcurrentvalue': result.closedCurrentValue,
                'totalinvestedamount': result.totalInvestedAmount,
                'totalamountout': result.totalAmountOut,
                'currentvalue': result.totalCurrentValue,
            }
        )

    def logSuccess(self, wallet: Wallet, periodDays: int,
                   result: PnlCalculationResult) -> None:
        """Log successful calculation with PnL breakdown."""
        openPnl = result.openAmountOut + result.openCurrentValue - result.openAmountInvested
        closedPnl = result.closedAmountOut - result.closedAmountInvested
        totalPnl = openPnl + closedPnl

        logger.info(
            "PNL_SCHEDULER :: SUCCESS | Wallet: %s | Period: %d days | "
            "Open PnL: $%.2f | Closed PnL: $%.2f | Total PnL: $%.2f",
            wallet.proxywallet[:10], periodDays,
            float(openPnl), float(closedPnl), float(totalPnl)
        )

    def buildResult(self, metrics: PnlSchedulerMetrics, duration: float,
                    startTime: datetime) -> dict:
        """Build result dictionary from metrics."""
        metricsDict = metrics.toDict()

        return {
            'totalWallets': metricsDict['totalWallets'],
            'totalCalculations': metricsDict['totalCalculations'],
            'succeeded': metricsDict['succeeded'],
            'failed': metricsDict['failed'],
            'errorCount': metricsDict['errorCount'],
            'errors': metricsDict['errors'],
            'periodStats': metricsDict['periodStats'],
            'durationSeconds': round(duration, 2),
            'startTime': startTime.strftime('%Y-%m-%d %H:%M:%S'),
            'workersUsed': PARALLEL_PNL_SCHEDULER_WORKERS
        }

    def buildEmptyResult(self, startTime: datetime) -> dict:
        """Build empty result for zero wallets."""
        return {
            'totalWallets': 0,
            'totalCalculations': 0,
            'succeeded': 0,
            'failed': 0,
            'errorCount': 0,
            'errors': [],
            'periodStats': {},
            'durationSeconds': 0.0,
            'startTime': startTime.strftime('%Y-%m-%d %H:%M:%S'),
            'workersUsed': PARALLEL_PNL_SCHEDULER_WORKERS
        }
