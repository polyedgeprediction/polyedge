"""
Position Current Value Updater - Bulk update calculatedcurrentvalue for all positions.
Updates positions in markets with open positions by summing amountremaining across all positions in each market.

Performance: Single UPDATE query with CTE for all markets and positions.
"""
import logging
from datetime import datetime, timezone
from django.db import connection

from positions.enums.PositionStatus import PositionStatus

logger = logging.getLogger(__name__)


class PositionCurrentValueUpdater:
    """
    Efficient bulk updater for position calculated current values.

    Uses PostgreSQL CTE (Common Table Expression) to:
    1. Identify markets with at least one open position
    2. Calculate sum of amountremaining per market
    3. Update all positions in those markets with the calculated total

    All operations done in a single UPDATE query for maximum efficiency.
    """

    @staticmethod
    def updateCalculatedCurrentValues() -> dict:
        """
        Update calculatedcurrentvalue for all positions in markets with open positions.

        For each market with open positions:
        - Sum amountremaining across all positions in the market
        - Set calculatedcurrentvalue = sum for ALL positions in that market

        Performance: Single bulk UPDATE query using CTE.

        Returns:
            dict with execution metrics:
                - marketsUpdated: Number of markets affected
                - positionsUpdated: Number of position records updated
                - durationSeconds: Execution time
        """
        startTime = datetime.now(timezone.utc)

        logger.info("POSITION_UPDATES_SCHEDULER :: POSITION_CURRENT_VALUE_UPDATER :: Started")

        # Single bulk UPDATE query with CTE
        query = """
            WITH market_wallet_totals AS (
                -- Calculate sum of amountremaining per wallet per market
                SELECT
                    p.marketsid,
                    p.walletsid,
                    SUM(p.amountremaining) as total_current_value
                FROM positions p
                WHERE EXISTS (
                    -- Only include (wallet, market) combinations with at least one open position
                    SELECT 1
                    FROM positions p2
                    WHERE p2.marketsid = p.marketsid
                    AND p2.walletsid = p.walletsid
                    AND p2.positionstatus = %s
                )
                GROUP BY p.marketsid, p.walletsid
            )
            UPDATE positions
            SET calculatedcurrentvalue = market_wallet_totals.total_current_value
            FROM market_wallet_totals
            WHERE positions.marketsid = market_wallet_totals.marketsid
            AND positions.walletsid = market_wallet_totals.walletsid
        """

        with connection.cursor() as cursor:
            cursor.execute(query, [PositionStatus.OPEN.value])
            positionsUpdated = cursor.rowcount

        duration = (datetime.now(timezone.utc) - startTime).total_seconds()

        logger.info("POSITION_UPDATES_SCHEDULER :: POSITION_CURRENT_VALUE_UPDATER :: Completed | %.2fs | Positions: %d",duration,positionsUpdated)
    
