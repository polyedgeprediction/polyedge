"""
Wallet job functions - WHAT to execute, not WHEN.
Pure functions with no scheduler dependencies.
"""
import logging

logger = logging.getLogger(__name__)


def fetchLeaderboardData():
    """
    Job function: Fetch and update leaderboard wallet data.
    Pure function - no scheduler coupling.
    """
    try:
        from wallets.Scheduler import Scheduler
        result = Scheduler.execute()
        
        logger.info(
            "WALLET_JOB :: Leaderboard fetch completed | Success: %s | Wallets: %d",
            result.get('success', False),
            result.get('walletsProcessed', 0)
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "WALLET_JOB :: Leaderboard fetch failed | Error: %s",
            str(e),
            exc_info=True
        )
        raise