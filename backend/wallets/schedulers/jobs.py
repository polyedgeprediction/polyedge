"""
Wallet job functions - WHAT to execute, not WHEN.
Pure functions with no scheduler dependencies.
"""
import logging

logger = logging.getLogger(__name__)


def discoverAndFilterWallets():
    """
    Job function: Discover high-performing wallets from leaderboard and filter them.
    Uses new market-level PNL calculation to fix merge/split corruption bug.
    Pure function - no scheduler coupling.
    """
    try:
        from wallets.services.SmartWalletDiscoveryService import SmartWalletDiscoveryService
        
        # Execute complete discovery and filtering pipeline
        smart_discovery_service = SmartWalletDiscoveryService()
        result = smart_discovery_service.discoverAndProcessWallets(minPnl=20000)
        
        logger.info(
            "WALLET_JOB :: Wallet discovery completed | Success: %s | Qualified: %d | Persisted: %d",
            result.success,
            result.qualified,
            result.walletsPersisted
        )
        
        return result.toDict()  # Convert POJO to dict for scheduler compatibility
        
    except Exception as e:
        logger.error(
            "WALLET_JOB :: Wallet discovery failed | Error: %s",
            str(e),
            exc_info=True
        )
        raise