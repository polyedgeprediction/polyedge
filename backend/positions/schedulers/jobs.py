"""
Position job functions - WHAT to execute, not WHEN.
Pure functions with no scheduler dependencies.
"""
import logging
from positions.schedulers.PositionUpdatesScheduler import PositionUpdatesScheduler

logger = logging.getLogger(__name__)


def   updateExistingPositions():
    try:
        result = PositionUpdatesScheduler.updatePositions()
        
        logger.info("POSITION_JOB :: Position updates completed | Success: %s | Wallets: %d | Updated: %d",result.success, result.walletsProcessed, result.totalUpdated)
        return result.toDict()
        
    except Exception as e:
        logger.info("POSITION_JOB :: Position updates failed | Error: %s",str(e), exc_info=True)
        raise