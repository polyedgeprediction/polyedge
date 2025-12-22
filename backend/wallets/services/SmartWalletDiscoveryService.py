"""
Production-grade Smart Wallet Discovery Service.
Main entry point for discovering and processing smart money wallets from leaderboard.

Flow:
1. Fetch wallet candidates from leaderboard API
2. Evaluate each candidate through filtering pipeline
3. Persist wallets that pass filtering with complete hierarchy
4. Track and report metrics
"""
import logging
import time
from typing import List

from wallets.smartwalletdiscovery.WalletEvaluvationService import WalletEvaluvationService
from wallets.services.WalletPersistenceService import WalletPersistenceService
from wallets.pojos.WalletCandidate import WalletCandidate
from wallets.pojos.WalletDiscoveryResult import WalletDiscoveryResult
from wallets.pojos.WalletDiscoveryMetrics import WalletDiscoveryMetrics
from wallets.smartwalletdiscovery.WalletCandidateFetcher import WalletCandidateFetcher
from wallets.pojos.WalletEvaluvationResult import WalletEvaluvationResult

logger = logging.getLogger(__name__)


class SmartWalletDiscoveryService:
    """
    Main service for discovering and processing smart money wallets.

    Pipeline:
    1. Fetch wallet candidates from leaderboard
    2. Evaluate candidates using Event → Market → Position hierarchy
    3. Persist wallets that pass filtering
    4. Track metrics and failures
    """

    def __init__(self):
        self.evaluvationService = WalletEvaluvationService()
        self.persistenceService = WalletPersistenceService()

    def filterWalletsFromLeaderboard(self, minPnl: float = 20000) -> WalletDiscoveryResult:
        startTime = time.time()

        try:
            logger.info("SMART_WALLET_DISCOVERY :: Starting pipeline | MinPNL: %.0f", minPnl)

            # Step 1: Fetch candidates from leaderboard
            candidateFetcher = WalletCandidateFetcher()
            candidates = candidateFetcher.fetchCandidates(minPnl=minPnl)

            if not candidates:
                logger.info("SMART_WALLET_DISCOVERY :: No candidates found from leaderboard")
                executionTime = round(time.time() - startTime, 2)
                return WalletDiscoveryResult.empty(executionTime)

            logger.info("SMART_WALLET_DISCOVERY :: Candidates fetched: %d", len(candidates))

            # Step 2: Process candidates through evaluation and persistence pipeline
            metrics = self.processCandidates(candidates)

            # Step 3: Build response with metrics
            executionTime = round(time.time() - startTime, 2)

            discoveryResult = WalletDiscoveryResult.success(
                candidatesFound=metrics.totalProcessed,
                qualified=metrics.passedEvaluation,
                rejected=metrics.rejectedCount,
                walletsPersisted=metrics.successfullyPersisted,
                positionsPersisted=metrics.positionsPersisted,
                executionTimeSeconds=executionTime,
                rejectionReasons=metrics.rejectionReasons
            )

            logger.info("SMART_WALLET_DISCOVERY :: Pipeline complete | Qualified: %d | Persisted: %d | Time: %.1fs",
                       discoveryResult.qualified,
                       discoveryResult.walletsPersisted,
                       executionTime)

            return discoveryResult

        except Exception as e:
            executionTime = round(time.time() - startTime, 2)
            logger.error("SMART_WALLET_DISCOVERY :: Pipeline failed: %s", str(e), exc_info=True)
            return WalletDiscoveryResult.failure(str(e), executionTime)

    def processCandidates(self, candidates: List[WalletCandidate]) -> WalletDiscoveryMetrics:
        logger.info("SMART_WALLET_DISCOVERY :: Processing %d candidates", len(candidates))

        metrics = WalletDiscoveryMetrics.create()

        for candidate in candidates:
            metrics.incrementProcessed()

            try:
                # Step 1: Evaluate wallet
                evaluationResult = self.evaluvationService.evaluateWallet(candidate)

                if evaluationResult.passed:
                    metrics.recordPassed(evaluationResult.positionCount)

                    logger.info("SMART_WALLET_DISCOVERY :: PASSED | Wallet: %s | Trades: %d | PNL: %.2f",candidate.proxyWallet[:10],evaluationResult.tradeCount,float(evaluationResult.combinedPnl))

                    # Step 2: Persist wallet and hierarchy
                    persistedWallets = self.persistenceService.persistWallet(evaluationResult)

                    if persistedWallets:
                        metrics.recordPersisted(len(persistedWallets))
                        logger.info("SMART_WALLET_DISCOVERY :: PERSISTED | Wallet: %s | Categories: %d",candidate.proxyWallet[:10],len(persistedWallets))
                    else:
                        logger.info("SMART_WALLET_DISCOVERY :: Persistence failed | Wallet: %s",candidate.proxyWallet[:10])

                else:
                    metrics.recordRejected(evaluationResult.failReason or "Unknown")
                    logger.info("SMART_WALLET_DISCOVERY :: REJECTED | Wallet: %s | Reason: %s",candidate.proxyWallet[:10],evaluationResult.failReason)

            except Exception as e:
                metrics.recordProcessingError()
                logger.info("SMART_WALLET_DISCOVERY :: Error processing wallet %s: %s",candidate.proxyWallet[:10], str(e), exc_info=True)

        logger.info("SMART_WALLET_DISCOVERY :: Batch complete | Processed: %d | Passed: %d | Persisted: %d",metrics.totalProcessed,metrics.passedEvaluation,metrics.successfullyPersisted)
        return metrics
