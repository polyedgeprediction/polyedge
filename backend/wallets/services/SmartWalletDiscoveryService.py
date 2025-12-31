"""
Production-grade Smart Wallet Discovery Service.
Main entry point for discovering and processing smart money wallets from leaderboard.

Flow:
1. Fetch wallet candidates from leaderboard API
2. Evaluate each candidate through filtering pipeline (in parallel)
3. Persist wallets that pass filtering with complete hierarchy (with locking)
4. Track and report metrics
"""
import logging
import time
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed


from wallets.smartwalletdiscovery.WalletEvaluvationService import WalletEvaluvationService
from wallets.services.WalletPersistenceService import WalletPersistenceService
from wallets.pojos.WalletCandidate import WalletCandidate
from wallets.pojos.WalletDiscoveryResult import WalletDiscoveryResult
from wallets.pojos.WalletDiscoveryMetrics import WalletDiscoveryMetrics
from wallets.smartwalletdiscovery.WalletCandidateFetcher import WalletCandidateFetcher
from wallets.pojos.WalletEvaluvationResult import WalletEvaluvationResult
from wallets.Constants import PARALLEL_WALLET_WORKERS
from wallets.models import Wallet

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

            # Step 2: Filter out wallets that already exist and are active
            filteredCandidates = self.filterExistingActiveWallets(candidates)
            
            if not filteredCandidates:
                logger.info("SMART_WALLET_DISCOVERY :: All candidates already exist as active wallets")
                executionTime = round(time.time() - startTime, 2)
                return WalletDiscoveryResult.empty(executionTime)

            logger.info("SMART_WALLET_DISCOVERY :: After filtering existing active wallets: %d candidates remaining", len(filteredCandidates))

            # Step 3: Process candidates through evaluation and persistence pipeline
            metrics = self.processCandidates(filteredCandidates)

            # Step 4: Build response with metrics
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
        logger.info("SMART_WALLET_DISCOVERY :: Processing %d candidates in parallel with %d workers",len(candidates), PARALLEL_WALLET_WORKERS)

        metrics = WalletDiscoveryMetrics.create()

        # Process candidates in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=PARALLEL_WALLET_WORKERS) as executor:
            # Submit all candidates for processing
            future_to_candidate = {
                executor.submit(self.processSingleCandidate, candidate, metrics): candidate
                for candidate in candidates
            }

            # Wait for all tasks to complete
            for future in as_completed(future_to_candidate):
                candidate = future_to_candidate[future]
                try:
                    future.result()  # This will raise any exception that occurred during processing
                except Exception as e:
                    logger.info("SMART_WALLET_DISCOVERY :: Unexpected error in parallel processing | #%d | Wallet: %s | Error: %s",candidate.number, candidate.proxyWallet[:10], str(e))
                    metrics.recordProcessingError()

        logger.info("SMART_WALLET_DISCOVERY :: Batch complete | Processed: %d | Passed: %d | Persisted: %d",metrics.totalProcessed, metrics.passedEvaluation, metrics.successfullyPersisted)
        return metrics

    def processSingleCandidate(self, candidate: WalletCandidate, metrics: WalletDiscoveryMetrics) -> None:
        metrics.incrementProcessed()

        try:
            # Step 1: Evaluate wallet
            evaluationResult = self.evaluvationService.evaluateWallet(candidate)

            if evaluationResult.passed:
                metrics.recordPassed(evaluationResult.positionCount)

                logger.info("SMART_WALLET_DISCOVERY :: PASSED | #%d | Wallet: %s | Trades: %d | PNL: %.2f",candidate.number, candidate.proxyWallet[:10], evaluationResult.tradeCount, float(evaluationResult.combinedPnl))

                # Step 2: Persist wallet and hierarchy (with database lock)
                persistedWallet = self.persistenceService.persistWallet(evaluationResult, candidate.number)

                if persistedWallet:
                    metrics.recordPersisted(1)
                    logger.info("SMART_WALLET_DISCOVERY :: PERSISTED | #%d | Wallet: %s | Categories: %s",candidate.number, candidate.proxyWallet[:10], persistedWallet.category or "None")
                else:
                    logger.info("SMART_WALLET_DISCOVERY :: Persistence failed | #%d | Wallet: %s",candidate.number, candidate.proxyWallet[:10])

            else:
                metrics.recordRejected(evaluationResult.failReason or "Unknown")
                logger.info("SMART_WALLET_DISCOVERY :: REJECTED | #%d | Wallet: %s | Reason: %s",candidate.number, candidate.proxyWallet[:10], evaluationResult.failReason)

        except Exception as e:
            metrics.recordProcessingError()
            logger.info("SMART_WALLET_DISCOVERY :: Error processing wallet | #%d | %s: %s",candidate.number, candidate.proxyWallet[:10], str(e), exc_info=True)

    def filterExistingActiveWallets(self, candidates: List[WalletCandidate]) -> List[WalletCandidate]:
        if not candidates:
            return candidates

        try:
            # Create set of candidate addresses for efficient query
            candidateAddresses = {candidate.proxyWallet for candidate in candidates}
            
            # Optimized query: get ONLY wallets that exist AND are active
            # This minimizes the result set size, reducing comparison time significantly
            # By querying only for active wallets, we avoid fetching unnecessary data
            # Query leverages index on proxywallet for fast lookups
            existingActiveAddresses = set(
                Wallet.objects.filter(
                    proxywallet__in=candidateAddresses,
                    isactive=1
                ).values_list('proxywallet', flat=True)
            )
            
            # Filter candidates: keep only those NOT in existingActiveAddresses
            # This means: wallets that don't exist OR exist but are not active
            # Set membership check is O(1), making comparison very fast
            filteredCandidates = [
                candidate for candidate in candidates
                if candidate.proxyWallet not in existingActiveAddresses
            ]
            
            filteredCount = len(candidates) - len(filteredCandidates)
            
            if filteredCount > 0:
                logger.info("SMART_WALLET_DISCOVERY :: Filtered out %d existing active wallets from %d candidates",
                           filteredCount, len(candidates))
            
            return filteredCandidates
            
        except Exception as e:
            logger.info("SMART_WALLET_DISCOVERY :: Error filtering existing active wallets: %s", str(e), exc_info=True)
            # On error, return all candidates to avoid blocking the pipeline
            return candidates
