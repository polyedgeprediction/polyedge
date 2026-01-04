"""
SQL query for Market Report.

Query Strategy:
1. Fetch all positions for a specific market (both open and closed)
2. Join with wallets to get wallet information
3. Join with walletpnl to get PnL ranges for 30, 60, 90 days
4. Return position-level data with wallet PnL metrics

Performance Optimizations:
- Uses joins for efficient data fetching
- Leverages indexes on market and wallet columns
- Returns only necessary columns
"""
import logging
from typing import List, Dict
from django.db import connection

from reports.pojos.marketreport.MarketReportRequest import MarketReportRequest

logger = logging.getLogger(__name__)

LOG_PREFIX = "[MARKET_REPORT_QUERY]"


class MarketReportQuery:
    """
    Executes SQL query to fetch all positions for a specific market.

    Returns position-level data with wallet and PnL information.
    """

    @staticmethod
    def execute(request: MarketReportRequest) -> List[Dict]:
        """
        Execute query to fetch market report data.

        Args:
            request: MarketReportRequest with marketId

        Returns:
            List of position rows with wallet and PnL data
        """
        return MarketReportQuery.executeQuery(marketId=request.marketId)

    @staticmethod
    def executeQuery(marketId: int) -> List[Dict]:
        """
        Execute SQL query to fetch all positions for a market.

        Query fetches:
        - All positions (open and closed) for the market
        - Wallet information
        - PnL metrics for 30, 60, 90 day periods

        Args:
            marketId: Database market ID (marketsid)

        Returns:
            List of position rows grouped by wallet
        """
        query = """
            SELECT
                -- Position details
                p.positionid,
                p.walletsid,
                p.marketsid,
                p.outcome,
                p.positionstatus,
                p.totalshares,
                p.currentshares,
                p.averageentryprice,
                p.amountspent,
                p.amountremaining,
                p.calculatedamountinvested,
                p.calculatedcurrentvalue,
                p.calculatedamountout,
                p.realizedpnl,
                p.unrealizedpnl,

                -- Wallet details
                w.proxywallet,
                w.username,
                w.category,
                w.pnl as wallet_total_pnl,

                -- 30-day PnL
                wp30.totalinvestedamount as pnl_30_invested,
                wp30.totalamountout as pnl_30_amount_out,
                wp30.currentvalue as pnl_30_current_value,
                wp30.realizedwinrate as pnl_30_realized_win_rate,
                wp30.realizedwinrateodds as pnl_30_realized_win_rate_odds,
                wp30.unrealizedwinrate as pnl_30_unrealized_win_rate,
                wp30.unrealizedwinrateodds as pnl_30_unrealized_win_rate_odds,

                -- 60-day PnL
                wp60.totalinvestedamount as pnl_60_invested,
                wp60.totalamountout as pnl_60_amount_out,
                wp60.currentvalue as pnl_60_current_value,
                wp60.realizedwinrate as pnl_60_realized_win_rate,
                wp60.realizedwinrateodds as pnl_60_realized_win_rate_odds,
                wp60.unrealizedwinrate as pnl_60_unrealized_win_rate,
                wp60.unrealizedwinrateodds as pnl_60_unrealized_win_rate_odds,

                -- 90-day PnL
                wp90.totalinvestedamount as pnl_90_invested,
                wp90.totalamountout as pnl_90_amount_out,
                wp90.currentvalue as pnl_90_current_value,
                wp90.realizedwinrate as pnl_90_realized_win_rate,
                wp90.realizedwinrateodds as pnl_90_realized_win_rate_odds,
                wp90.unrealizedwinrate as pnl_90_unrealized_win_rate,
                wp90.unrealizedwinrateodds as pnl_90_unrealized_win_rate_odds

            FROM positions p
            INNER JOIN wallets w ON p.walletsid = w.walletsid
            LEFT JOIN walletpnl wp30 ON w.walletsid = wp30.walletid AND wp30.period = 30
            LEFT JOIN walletpnl wp60 ON w.walletsid = wp60.walletid AND wp60.period = 60
            LEFT JOIN walletpnl wp90 ON w.walletsid = wp90.walletid AND wp90.period = 90
            WHERE p.marketsid = %s
            ORDER BY w.walletsid, p.outcome
        """

        try:
            with connection.cursor() as cursor:
                cursor.execute(query, [marketId])
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]

            logger.info("%s :: Query executed | MarketId: %d | Rows: %d",
                        LOG_PREFIX, marketId, len(results))

            return results

        except Exception as e:
            logger.exception("%s :: Query failed | MarketId: %d | Error: %s",
                           LOG_PREFIX, marketId, str(e))
            raise
