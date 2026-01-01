"""
Position Limit Validation Utilities.

Simple, modular functions for validating position counts against limits.
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from dateutil import parser as dateParser

from positions.pojos.PolymarketPositionResponse import PolymarketPositionResponse
from positions.enums.PositionStatus import PositionStatus
from wallets.Constants import (
    MAX_OPEN_POSITIONS_WITH_FUTURE_END_DATE,
    MAX_CLOSED_POSITIONS
)

logger = logging.getLogger(__name__)


def countValidOpenPositions(openPositions: List[PolymarketPositionResponse]) -> int:
    """
    Count open positions where endDate > current UTC time.
    
    Rules:
    - Only count positions with valid endDate
    - Convert endDate to end of day timestamp (23:59:59)
    - Compare with current UTC timestamp
    - If endDate is missing or invalid, ignore the position
    
    Args:
        openPositions: List of open positions
        
    Returns:
        Count of valid open positions with future endDate
    """
    currentUtcTimestamp = int(datetime.now(timezone.utc).timestamp())
    count = 0
    
    for position in openPositions:
        if position.positionType != PositionStatus.OPEN:
            continue
            
        endDateTimestamp = _parseEndDateToTimestamp(position.endDate)
        if endDateTimestamp is None:
            # Missing or invalid endDate - ignore in counting
            continue
            
        # Count only if endDate is in the future
        if endDateTimestamp > currentUtcTimestamp:
            count += 1
            
    return count


def validatePositionLimits(
    openPositions: List[PolymarketPositionResponse],
    closedPositions: List[PolymarketPositionResponse],
    walletAddress: str,
    candidateNumber: Optional[int] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate position counts against limits.
    
    Args:
        openPositions: List of open positions
        closedPositions: List of closed positions
        walletAddress: Wallet address for logging
        candidateNumber: Optional candidate number for logging
        
    Returns:
        Tuple of (isValid, failureReason)
        - isValid: True if limits are not exceeded, False otherwise
        - failureReason: None if valid, descriptive string if invalid
    """
    # Validate open positions
    openCount = countValidOpenPositions(openPositions)
    if openCount > MAX_OPEN_POSITIONS_WITH_FUTURE_END_DATE:
        reason = (
            f"Open positions with future endDate exceed limit | "
            f"Count: {openCount} | Limit: {MAX_OPEN_POSITIONS_WITH_FUTURE_END_DATE}"
        )
        logPrefix = f"Candidate #{candidateNumber} | " if candidateNumber is not None else ""
        logger.info(
            "POSITION_LIMIT_VALIDATOR :: REJECTED | %sWallet: %s | %s",
            logPrefix,
            walletAddress[:10],
            reason
        )
        return False, reason

    # Validate closed positions
    closedCount = len(closedPositions)
    if closedCount > MAX_CLOSED_POSITIONS:
        reason = (
            f"Closed positions exceed limit | "
            f"Count: {closedCount} | Limit: {MAX_CLOSED_POSITIONS}"
        )
        logPrefix = f"Candidate #{candidateNumber} | " if candidateNumber is not None else ""
        logger.info(
            "POSITION_LIMIT_VALIDATOR :: REJECTED | %sWallet: %s | %s",
            logPrefix,
            walletAddress[:10],
            reason
        )
        return False, reason

    # All limits passed
    logPrefix = f"Candidate #{candidateNumber} | " if candidateNumber is not None else ""
    logger.info(
        "POSITION_LIMIT_VALIDATOR :: PASSED | %sWallet: %s | "
        "Open (future endDate): %d/%d | Closed: %d/%d",
        logPrefix,
        walletAddress[:10],
        openCount,
        MAX_OPEN_POSITIONS_WITH_FUTURE_END_DATE,
        closedCount,
        MAX_CLOSED_POSITIONS
    )
    return True, None


def _parseEndDateToTimestamp(endDate: Optional[str]) -> Optional[int]:
    """
    Parse endDate string to Unix timestamp at end of day (23:59:59).
    
    Handles multiple date formats:
    - "YYYY-MM-DD" (e.g., "2026-12-31")
    - "YYYY-MM-DDTHH:MM:SSZ" (e.g., "1970-01-01T00:00:00Z")
    
    Args:
        endDate: Date string or None
        
    Returns:
        Unix timestamp at 23:59:59.999999 of the date, or None if parsing fails
    """
    if not endDate:
        return None
        
    try:
        # Parse the date string (handles both formats)
        parsedDate = dateParser.parse(endDate)
        
        # Set time to end of day (23:59:59.999999)
        endOfDay = parsedDate.replace(
            hour=23,
            minute=59,
            second=59,
            microsecond=999999
        )
        
        # Ensure timezone awareness (UTC)
        if endOfDay.tzinfo is None:
            endOfDay = endOfDay.replace(tzinfo=timezone.utc)
        else:
            endOfDay = endOfDay.astimezone(timezone.utc)
            
        return int(endOfDay.timestamp())
        
    except Exception as e:
        logger.debug(
            "POSITION_LIMIT_VALIDATOR :: Failed to parse endDate: %s | Error: %s",
            endDate,
            str(e)
        )
        return None
