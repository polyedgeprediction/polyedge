"""
Main orchestrator that coordinates discovery, filtering, and persistence.
"""
import logging
from typing import List, Dict
from wallets.discovery.WalletCandidateFetcher import WalletCandidateFetcher
from wallets.discovery.WalletFilteringService import WalletFilteringService
from wallets.discovery.WalletFilterPersistenceHandler import WalletFilterPersistenceHandler
from wallets.pojos.WalletFilterResult import WalletFilterResult

logger = logging.getLogger(__name__)


class WalletDiscoveryScheduler:
    """
    Main orchestrator that coordinates discovery, filtering, and persistence.
    """
    
    def __init__(self):
        self.candidateFetcher = WalletCandidateFetcher()
        self.filteringService = WalletFilteringService()
        self.persistenceHandler = WalletFilterPersistenceHandler()
    
    @staticmethod
    def execute(minPnl: float = 20000) -> Dict[str, any]:
        """
        Entry point. Called by scheduler.
        
        Returns:
            {
                'success': bool,
                'candidates_found': int,
                'qualified': int,
                'rejected': int,
                'wallets_persisted': int,
                'positions_persisted': int,
                'execution_time_seconds': float,
                'rejection_reasons': Dict[str, int]
            }
        """
        import time
        startTime = time.time()
        
        logger.info("WALLET_DISCOVERY_SCHEDULER :: Starting wallet discovery and filtering")
        
        try:
            scheduler = WalletDiscoveryScheduler()
            
            # Step 1: Discover and filter wallets
            successfulWallets, failedWallets = scheduler.discoverAndFilterWallets(minPnl=minPnl)
            
            # Step 2: Persist qualified wallets (no filtering needed)
            persistenceStats = scheduler.persistQualifiedWallets(successfulWallets)
            
            # Step 3: Compile final statistics
            allResults = successfulWallets + failedWallets
            stats = scheduler._compileStatistics(allResults, persistenceStats, startTime)
            
            logger.info("WALLET_DISCOVERY_SCHEDULER :: Completed successfully | Stats: %s", stats)
            return stats
            
        except Exception as e:
            executionTime = time.time() - startTime
            logger.error("WALLET_DISCOVERY_SCHEDULER :: Failed with error: %s", str(e), exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'execution_time_seconds': executionTime,
                'candidates_found': 0,
                'qualified': 0,
                'rejected': 0,
                'wallets_persisted': 0,
                'positions_persisted': 0
            }

    @staticmethod
    def _filterProvidedWallets(walletAddresses: List[str]) -> Dict[str, any]:
        """
        Filter provided wallet addresses through the same system as discovery.
        
        Args:
            walletAddresses: List of wallet addresses to filter
            
        Returns:
            Same format as execute() method
        """
        import time
        from wallets.pojos.WalletCandidate import WalletCandidate
        from decimal import Decimal
        
        startTime = time.time()
        scheduler = WalletDiscoveryScheduler()
        
        try:
            # Convert wallet addresses to candidates
            candidates = [
                WalletCandidate(
                    proxyWallet=address,
                    username=address[:10],
                    allTimePnl=Decimal('0'),
                    allTimeVolume=Decimal('0')
                )
                for address in walletAddresses
            ]
            
            # Filter candidates using existing logic
            successfulWallets = []
            failedWallets = []
            
            for candidate in candidates:
                result = scheduler.filteringService.evaluateWallet(candidate)
                if result.passed:
                    successfulWallets.append(result)
                else:
                    failedWallets.append(result)
            
            # Persist successful wallets
            persistenceStats = scheduler.persistQualifiedWallets(successfulWallets)
            
            # Compile statistics
            allResults = successfulWallets + failedWallets
            return scheduler._compileStatistics(allResults, persistenceStats, startTime)
            
        except Exception as e:
            executionTime = time.time() - startTime
            logger.error("WALLET_DISCOVERY_SCHEDULER :: Error filtering provided wallets: %s", str(e), exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'execution_time_seconds': executionTime,
                'candidates_found': len(walletAddresses),
                'qualified': 0,
                'rejected': len(walletAddresses),
                'wallets_persisted': 0,
                'positions_persisted': 0
            }
    
    def discoverAndFilterWallets(self, minPnl: float = 20000) -> tuple[List[WalletFilterResult], List[WalletFilterResult]]:
        """
        Step 1: Fetch candidates from leaderboard (period='all', PNL > 20K)
        Step 2: For each candidate, run filteringService.evaluateWallet()
        Step 3: Collect results (both passed and failed for logging)
        
        Returns tuple of (successfulWallets, failedWallets).
        """
        logger.info("WALLET_DISCOVERY_SCHEDULER :: Starting candidate discovery")
        
        # Fetch candidates from leaderboard
        candidates = self.candidateFetcher.fetchCandidates(minPnl=minPnl)
        
        if not candidates:
            logger.warning("WALLET_DISCOVERY_SCHEDULER :: No candidates found from leaderboard")
            return [], []
        
        logger.info("WALLET_DISCOVERY_SCHEDULER :: Found %d candidates | Starting filtering", len(candidates))
        
        # Filter each candidate - separate successful and failed wallets
        successfulWallets = []
        failedWallets = []
        
        for i, candidate in enumerate(candidates):
            try:
                logger.info("WALLET_DISCOVERY_SCHEDULER :: Filtering candidate %d/%d: %s", 
                           i+1, len(candidates), candidate.proxyWallet[:10])
                
                wallet = self.filteringService.evaluateWallet(candidate)
                
                if wallet.passed:
                    successfulWallets.append(wallet)
                    logger.info("WALLET_DISCOVERY_SCHEDULER :: Candidate PASSED | Address: %s | PNL: %.2f",wallet.walletAddress[:10], float(wallet.combinedPnl))
                else:
                    failedWallets.append(wallet)
                    logger.info("WALLET_DISCOVERY_SCHEDULER :: Candidate REJECTED | Address: %s | Reason: %s",wallet.walletAddress[:10], wallet.failReason)
                
            except Exception as e:
                logger.info("WALLET_DISCOVERY_SCHEDULER :: Error filtering candidate %s: %s", candidate.proxyWallet[:10], str(e))
                # Create failed result for statistics
                failedWallet = WalletFilterResult(walletAddress=candidate.proxyWallet,passed=False,failReason=f"WALLET_DISCOVERY_SCHEDULER :: Filtering error | Error: {str(e)[:50]}",candidate=candidate)
                failedWallets.append(failedWallet)
        
        qualified = len(successfulWallets)
        rejected = len(failedWallets)
        total = qualified + rejected
        
        logger.info("WALLET_DISCOVERY_SCHEDULER :: Filtering completed | Total: %d | Qualified: %d | Rejected: %d", total, qualified, rejected)
        
        # Return separate lists for efficient processing
        return successfulWallets, failedWallets
    
    def persistQualifiedWallets(self, successfulWallets: List[WalletFilterResult]) -> Dict[str, int]:
        """
        Persist successful wallets directly (no filtering needed).
        Delegate to persistenceHandler.
        
        Key: Reuses position data already collected during filtering.
        """
        if not successfulWallets:
            logger.info("WALLET_DISCOVERY_SCHEDULER :: No qualified wallets to persist")
            return {'wallets': 0, 'events': 0, 'markets': 0, 'positions': 0}
        
        logger.info("WALLET_DISCOVERY_SCHEDULER :: Starting persistence | Qualified wallets: %d", len(successfulWallets))
        
        persistenceStats = self.persistenceHandler.persistQualifiedWallets(successfulWallets)
        
        logger.info("WALLET_DISCOVERY_SCHEDULER :: Persistence completed | Stats: %s", persistenceStats)
        
        return persistenceStats
    
    def _compileStatistics(
        self, 
        results: List[WalletFilterResult], 
        persistenceStats: Dict[str, int], 
        startTime: float
    ) -> Dict[str, any]:
        """
        Compile comprehensive statistics for reporting.
        """
        import time
        executionTime = time.time() - startTime
        
        qualified = len([r for r in results if r.passed])
        rejected = len(results) - qualified
        
        # Analyze rejection reasons
        rejectionReasons = {}
        for result in results:
            if not result.passed and result.failReason:
                reason = result.failReason.split('_')[0]  # Get main reason category
                rejectionReasons[reason] = rejectionReasons.get(reason, 0) + 1
        
        return {
            'success': True,
            'execution_time_seconds': round(executionTime, 2),
            'candidates_found': len(results),
            'qualified': qualified,
            'rejected': rejected,
            'qualification_rate_percent': round((qualified / len(results)) * 100, 2) if results else 0,
            'wallets_persisted': persistenceStats.get('wallets', 0),
            'events_persisted': persistenceStats.get('events', 0),
            'markets_persisted': persistenceStats.get('markets', 0),
            'positions_persisted': persistenceStats.get('positions', 0),
            'rejection_reasons': rejectionReasons
        }