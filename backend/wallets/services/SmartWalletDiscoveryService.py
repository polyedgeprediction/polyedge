"""
Smart Wallet Discovery Service - Main integration point for wallet filtering and persistence.
Combines the filtering pipeline with persistence for complete wallet processing.
"""
import logging
from typing import List, Optional, Dict
from decimal import Decimal

from wallets.discovery.WalletFilteringService import WalletFilteringService
from wallets.services.WalletPersistenceService import WalletPersistenceService
from wallets.pojos.WalletCandidate import WalletCandidate
from wallets.pojos.WalletFilterResult import WalletFilterResult
from wallets.pojos.WalletDiscoveryResult import WalletDiscoveryResult
from wallets.pojos.WalletProcessingResult import WalletProcessingResult
from wallets.models import Wallet
from wallets.discovery.WalletCandidateFetcher import WalletCandidateFetcher
import time

logger = logging.getLogger(__name__)


class SmartWalletDiscoveryService:
    """
    Main service for discovering and processing smart money wallets.
    
    Handles the complete pipeline:
    1. Fetch wallet candidates from leaderboard
    2. Filter wallet candidates using market-level PNL calculation
    3. Persist wallets that pass filtering with all related data
    4. Track processing metrics and failures
    """
    
    def __init__(self):
        self.filtering_service = WalletFilteringService()
        self.persistence_service = WalletPersistenceService()
    
    def discoverAndProcessWallets(self, minPnl: float = 20000) -> WalletDiscoveryResult:
        start_time = time.time()
        
        try:
            logger.info("SMART_WALLET_DISCOVERY :: Starting wallet discovery pipeline (minPnl=%.0f)", minPnl)
            
            # Step 1: Fetch candidates from leaderboard
            candidate_fetcher = WalletCandidateFetcher()
            candidates = candidate_fetcher.fetchCandidates(minPnl=minPnl)
            
            if not candidates:
                logger.warning("SMART_WALLET_DISCOVERY :: No candidates found from leaderboard")
                execution_time = round(time.time() - start_time, 2)
                return WalletDiscoveryResult.empty(execution_time)
            
            logger.info("SMART_WALLET_DISCOVERY :: Found %d candidates, processing...", len(candidates))
            
            # Step 2: Process candidates through filtering and persistence pipeline
            processing_result = self.processWalletCandidates(candidates)
            
            # Step 3: Build clean POJO response
            execution_time = round(time.time() - start_time, 2)
            
            # Convert failure reasons to summary format
            rejection_reasons = {}
            for failure in processing_result.failedFiltering:
                if isinstance(failure, dict) and 'reason' in failure:
                    reason_key = failure['reason'].split(' |')[0].replace('Insufficient ', '').lower()
                    rejection_reasons[reason_key] = rejection_reasons.get(reason_key, 0) + 1
            
            result = WalletDiscoveryResult.success(
                candidatesFound=processing_result.totalProcessed,
                qualified=processing_result.passedFiltering,
                rejected=processing_result.rejectedCount,
                walletsPersisted=processing_result.successfullyPersisted,
                positionsPersisted=0,  # Not tracked separately in new system
                executionTimeSeconds=execution_time,
                rejectionReasons=rejection_reasons
            )
            
            logger.info("SMART_WALLET_DISCOVERY :: Pipeline completed | Qualified: %d | Persisted: %d | Time: %.1fs",
                       result.qualified, result.walletsPersisted, execution_time)
            
            return result
            
        except Exception as e:
            execution_time = round(time.time() - start_time, 2)
            logger.error("SMART_WALLET_DISCOVERY :: Pipeline failed: %s", str(e), exc_info=True)
            return WalletDiscoveryResult.failure(str(e), execution_time)
    
    def processWalletCandidates(self, candidates: List[WalletCandidate]) -> WalletProcessingResult:
        logger.info("SMART_WALLET_DISCOVERY :: Processing %d wallet candidates", len(candidates))
        
        results = WalletProcessingResult.create()
        
        passed_results = []
        
        for candidate in candidates:
            results.totalProcessed += 1
            
            try:
                # Step 1: Filter wallet using market-level PNL calculation
                filter_result = self.filtering_service.evaluateWallet(candidate)
                
                if filter_result.passed:
                    results.passedFiltering += 1
                    passed_results.append(filter_result)
                    logger.info("SMART_WALLET_DISCOVERY :: Wallet PASSED filtering: %s | Trades: %d | PNL: %.2f",
                               candidate.proxyWallet[:10], filter_result.tradeCount, 
                               float(filter_result.combinedPnl))
                    
                    # Step 2: Persist wallet and all related data
                    persisted_wallet = self.persistence_service.persistWalletFilterResult(filter_result)
                    
                    if persisted_wallet:
                        results.successfullyPersisted += 1
                        logger.info("SMART_WALLET_DISCOVERY :: Wallet PERSISTED successfully: %s (ID: %d)",
                                   persisted_wallet.proxywallet[:10], persisted_wallet.walletsid)
                    else:
                        results.addFailedPersistence(candidate.proxyWallet)
                        logger.error("SMART_WALLET_DISCOVERY :: Wallet PERSISTENCE FAILED: %s", candidate.proxyWallet[:10])
                
                else:
                    results.addFailedFiltering({
                        'address': candidate.proxyWallet,
                        'reason': filter_result.failReason
                    })
                    logger.debug("SMART_WALLET_DISCOVERY :: Wallet FAILED filtering: %s | Reason: %s",
                                candidate.proxyWallet[:10], filter_result.failReason)
                
            except Exception as e:
                logger.error("SMART_WALLET_DISCOVERY :: Error processing wallet %s: %s", candidate.proxyWallet[:10], str(e), exc_info=True)
                results.addFailedFiltering({
                    'address': candidate.proxyWallet,
                    'reason': f"Processing error: {str(e)[:50]}"
                })
        
        # Calculate metrics for passed wallets
        results.updateMetrics(passed_results)
        
        logger.info("Batch processing complete | Processed: %d | Passed: %d | Persisted: %d",
                   results.totalProcessed, results.passedFiltering, results.successfullyPersisted)
        
        return results
    
    def processSingleWallet(self, candidate: WalletCandidate) -> tuple[Optional[Wallet], WalletFilterResult]:
        """
        Process a single wallet candidate through the complete pipeline.
        
        Args:
            candidate: Wallet candidate to process
            
        Returns:
            (persisted_wallet, filter_result): Tuple of persisted wallet (if successful) and filter result
        """
        logger.info("Processing single wallet: %s", candidate.proxyWallet[:10])
        
        try:
            # Step 1: Filter wallet
            filter_result = self.filtering_service.evaluateWallet(candidate)
            
            if not filter_result.passed:
                logger.info("Wallet failed filtering: %s | Reason: %s",
                           candidate.proxyWallet[:10], filter_result.failReason)
                return None, filter_result
            
            logger.info("Wallet passed filtering: %s | Trades: %d | Positions: %d | PNL: %.2f",
                       candidate.proxyWallet[:10], filter_result.tradeCount, 
                       filter_result.positionCount, float(filter_result.combinedPnl))
            
            # Step 2: Persist wallet
            persisted_wallet = self.persistence_service.persistWalletFilterResult(filter_result)
            
            if persisted_wallet:
                logger.info("Wallet persisted successfully: %s (ID: %d)",
                           persisted_wallet.proxywallet[:10], persisted_wallet.walletsid)
            else:
                logger.error("Failed to persist wallet: %s", candidate.proxyWallet[:10])
            
            return persisted_wallet, filter_result
            
        except Exception as e:
            logger.error("Error processing wallet %s: %s", candidate.proxyWallet[:10], str(e), exc_info=True)
            
            # Create error result
            error_result = WalletFilterResult(
                walletAddress=candidate.proxyWallet,
                passed=False,
                failReason=f"Processing error: {str(e)[:100]}",
                candidate=candidate
            )
            
            return None, error_result
    
    def validateFilterResult(self, result: WalletFilterResult) -> bool:
        """
        Validate that a filter result has all required data for persistence.
        """
        if not result.passed:
            return True  # Failed results don't need validation
        
        try:
            # Check required fields
            if not result.walletAddress:
                logger.error("Filter result missing wallet address")
                return False
            
            if not result.candidate:
                logger.error("Filter result missing candidate data")
                return False
            
            # Check market categorization
            if not result.needtradesMarkets and not result.dontneedtradesMarkets:
                logger.warning("Filter result has no markets - unusual but not invalid")
            
            # Check that needtrades markets have required trade data
            for conditionId, marketData in result.needtradesMarkets.items():
                if 'dailyTradesMap' not in marketData:
                    logger.error("needtrades market %s missing dailyTradesMap", conditionId[:10])
                    return False
                
                if 'positions' not in marketData:
                    logger.error("needtrades market %s missing positions", conditionId[:10])
                    return False
            
            # Check PNL calculation consistency
            calculated_combined = result.needtradesPnl + result.dontneedtradesPnl
            if abs(calculated_combined - result.combinedPnl) > Decimal('0.01'):
                logger.warning("PNL calculation inconsistency: combined=%.2f, calculated=%.2f",
                              float(result.combinedPnl), float(calculated_combined))
            
            return True
            
        except Exception as e:
            logger.error("Error validating filter result: %s", str(e))
            return False
    
    def getProcessingStats(self) -> Dict[str, any]:
        """
        Get current processing statistics from the database.
        
        Returns:
            Dict with current stats:
            {
                'total_wallets': int,
                'new_wallets': int,
                'old_wallets': int,
                'total_positions': int,
                'total_trades': int,
                'total_markets': int,
                'avg_pnl_per_wallet': float
            }
        """
        try:
            from django.db.models import Count, Sum, Avg
            from wallets.enums import WalletType
            
            stats = {
                'total_wallets': Wallet.objects.count(),
                'new_wallets': Wallet.objects.filter(wallettype=WalletType.NEW).count(),
                'old_wallets': Wallet.objects.filter(wallettype=WalletType.OLD).count(),
                'total_positions': Wallet.objects.aggregate(
                    total=Count('positions')
                )['total'] or 0,
                'total_trades': Wallet.objects.aggregate(
                    total=Count('trades')
                )['total'] or 0,
                'total_markets': Market.objects.count() if 'Market' in globals() else 0,
            }
            
            # Calculate average PNL (this is complex with market-level calculation, so approximate)
            pnl_data = Wallet.objects.aggregate(
                avg_realized=Avg('positions__realizedpnl'),
                avg_unrealized=Avg('positions__unrealizedpnl')
            )
            
            stats['avg_pnl_per_wallet'] = float(
                (pnl_data['avg_realized'] or 0) + (pnl_data['avg_unrealized'] or 0)
            )
            
            return stats
            
        except Exception as e:
            logger.error("Error getting processing stats: %s", str(e))
            return {'error': str(e)}