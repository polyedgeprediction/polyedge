"""
Position job functions - WHAT to execute, not WHEN.
Pure functions with no scheduler dependencies.
"""
import logging

logger = logging.getLogger(__name__)


def fetchNewWalletPositions():
    """
    Job function: Fetch positions for NEW wallets.
    Pure function - no scheduler coupling.
    """
    try:
        from positions.schedulers.FetchNewWalletPositionsScheduler import FetchNewWalletPositionsScheduler
        result = FetchNewWalletPositionsScheduler.execute()
        
        logger.info(
            "POSITION_JOB :: New wallet positions completed | Success: %s | Wallets: %d",
            result.get('success', False),
            result.get('walletsProcessed', 0)
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "POSITION_JOB :: New wallet positions failed | Error: %s",
            str(e),
            exc_info=True
        )
        raise


def updateExistingPositions():
    """
    Job function: Update positions for OLD wallets.
    Pure function - no scheduler coupling.
    """
    try:
        from positions.schedulers.PositionUpdatesScheduler import PositionUpdatesScheduler
        result = PositionUpdatesScheduler.execute()
        
        logger.info(
            "POSITION_JOB :: Position updates completed | Success: %s | Wallets: %d | Updated: %d",
            result.success,
            result.walletsProcessed,
            result.totalUpdated
        )
        
        return result.toDict()
        
    except Exception as e:
        logger.error(
            "POSITION_JOB :: Position updates failed | Error: %s",
            str(e),
            exc_info=True
        )
        raise