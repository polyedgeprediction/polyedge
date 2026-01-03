"""
Optimized SQL query for Smart Money Concentration Report.

Query Strategy:
1. CTE: Identify qualifying wallets (PNL >= threshold for period)
2. Join positions with qualifying wallets
3. Filter by minimum investment per wallet in market
4. Include market and event details
5. Return position-level data for aggregation in Python

Performance Optimizations:
- Uses CTEs for query plan optimization
- Leverages indexes on wallet, period, and market columns
- Filters early to reduce intermediate result set
- Returns only necessary columns
"""
import logging
from typing import List, Dict, Optional
from datetime import date
from django.db import connection

from reports.pojos.smartmoneyconcentration.SmartMoneyConcentrationRequest import SmartMoneyConcentrationRequest
from reports.Constants import LOG_PREFIX_SMART_MONEY_CONCENTRATION as LOG_PREFIX

logger = logging.getLogger(__name__)


class SmartMoneyConcentrationQuery:
    """
    Executes optimized SQL query to fetch smart money positions.
    
    Query returns position-level data that is then aggregated by the generator
    to handle the edge case where market-wise calculated amounts are duplicated
    across positions.
    """
    
    @staticmethod
    def execute(request: SmartMoneyConcentrationRequest) -> List[Dict]:
        return SmartMoneyConcentrationQuery.executeQuery(
            pnlPeriod=request.pnlPeriod,
            minWalletPnl=float(request.minWalletPnl),
            minInvestmentAmount=float(request.minInvestmentAmount),
            category=request.category,
            endDateFrom=request.endDateFrom,
            endDateTo=request.endDateTo
        )

    @staticmethod
    def executeQuery(
        pnlPeriod: int, 
        minWalletPnl: float,
        minInvestmentAmount: float,
        category: Optional[str],
        endDateFrom: Optional[date] = None,
        endDateTo: Optional[date] = None
    ) -> List[Dict]:
        """
        Execute optimized SQL query to fetch smart money concentration data.
        
        Query Strategy:
        1. CTE: Identify qualifying wallets (PNL >= threshold)
        2. Join positions with qualifying wallets (only open positions)
        3. Filter by minimum investment (market-wise, per wallet)
        4. Filter by end date range if provided
        5. Include market and event details
        
        Edge Case Handling:
        - calculatedamountinvested/calculatedcurrentvalue are market-wise
        - Multiple positions in same market have identical values
        - We return position-level data; aggregation happens in Python
        - Only open positions (positionstatus = 1) are included
        
        Returns:
            List of position rows with wallet, market, and event data
        """
        # Build params list - order must match placeholder order in query
        params = [pnlPeriod, minWalletPnl]
        
        # Build dynamic category clause
        categoryClause = ""
        if category:
            categoryClause = "AND w.category ILIKE %s"
            params.append(f"%{category}%")
        
        # Add minInvestmentAmount (matches placeholder order in qualifying_positions)
        params.append(minInvestmentAmount)
        
        # Build dynamic end date clause for qualifying_positions
        endDateClause = ""
        if endDateFrom:
            endDateClause += "AND p.enddate >= %s "
            params.append(endDateFrom)
        if endDateTo:
            endDateClause += "AND p.enddate <= %s "
            params.append(endDateTo)
        
        query = """
            WITH qualifying_wallets AS (
                -- Step 1: Find wallets with PNL >= threshold for the period
                -- PNL = (totalamountout + currentvalue) - totalinvestedamount
                SELECT 
                    wp.walletid,
                    w.proxywallet,
                    w.username,
                    w.category,
                    (wp.totalamountout + wp.currentvalue - wp.totalinvestedamount) as period_pnl
                FROM walletpnl wp
                INNER JOIN wallets w ON wp.walletid = w.walletsid
                WHERE wp.period = %s
                AND w.isactive = 1
                AND (wp.totalamountout + wp.currentvalue - wp.totalinvestedamount) >= %s
                {category_clause}
            ),
            qualifying_positions AS (
                -- Step 2: Find positions that qualify:
                -- - Open position (positionstatus = 1)
                -- - End date in future (enddate > NOW)
                -- - Market-wise investment >= threshold
                -- - End date within optional date range filter
                SELECT 
                    p.positionid,
                    p.walletsid,
                    p.marketsid,
                    p.conditionid,
                    p.outcome,
                    p.positionstatus,
                    p.enddate,
                    p.amountspent,
                    p.amountremaining,
                    p.calculatedamountinvested,
                    p.calculatedcurrentvalue,
                    p.calculatedamountout,
                    p.averageentryprice
                FROM positions p
                WHERE p.positionstatus = 1
                AND p.enddate > NOW()
                AND p.calculatedamountinvested >= %s
                {end_date_clause}
            ),
            qualifying_wallet_markets AS (
                -- Step 3: Get distinct wallet-market combinations
                SELECT DISTINCT qw.walletid, qp.marketsid
                FROM qualifying_wallets qw
                INNER JOIN qualifying_positions qp ON qp.walletsid = qw.walletid
            ),
            qualifying_markets AS (
                -- Step 4: Get distinct markets with smart money
                SELECT DISTINCT marketsid
                FROM qualifying_wallet_markets
            )
            -- Step 5: Get all qualifying positions with wallet and market details
            SELECT 
                qp.positionid,
                qp.walletsid,
                qw.proxywallet,
                qw.username,
                qw.period_pnl,
                qp.marketsid,
                qp.conditionid,
                qp.outcome,
                qp.positionstatus,
                qp.amountspent as position_invested,
                qp.amountremaining as position_current_value,
                qp.calculatedamountinvested,
                qp.calculatedcurrentvalue,
                qp.calculatedamountout,
                qp.averageentryprice,
                m.marketslug,
                m.question,
                m.volume as market_volume,
                m.liquidity as market_liquidity,
                m.enddate as market_enddate,
                m.closedtime,
                e.eventid,
                e.eventslug,
                e.title as event_title
            FROM qualifying_positions qp
            INNER JOIN qualifying_wallets qw ON qp.walletsid = qw.walletid
            INNER JOIN qualifying_markets qm ON qp.marketsid = qm.marketsid
            INNER JOIN markets m ON qp.marketsid = m.marketsid
            INNER JOIN events e ON m.eventsid = e.eventid
            ORDER BY qp.marketsid, qp.outcome, qp.calculatedamountinvested DESC
        """.format(category_clause=categoryClause, end_date_clause=endDateClause)
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            logger.info("%s :: Query executed | Rows: %d | Period: %d | MinPnL: %.0f | MinInvest: %.0f | EndDateFrom: %s | EndDateTo: %s",
                        LOG_PREFIX, len(results), pnlPeriod, minWalletPnl, minInvestmentAmount, endDateFrom, endDateTo)
            
            return results
            
        except Exception as e:
            logger.exception("%s :: Query failed | Period: %d | Error: %s", LOG_PREFIX, pnlPeriod, str(e))
            raise

    @staticmethod
    def getQualifyingWalletCount(pnlPeriod: int, minWalletPnl: float, category: Optional[str] = None) -> int:
        params = [pnlPeriod, minWalletPnl]
        
        categoryClause = ""
        if category:
            categoryClause = "AND w.category ILIKE %s"
            params.append(f"%{category}%")
        
        query = """
            SELECT COUNT(DISTINCT wp.walletid)
            FROM walletpnl wp
            INNER JOIN wallets w ON wp.walletid = w.walletsid
            WHERE wp.period = %s
            AND w.isactive = 1
            AND (wp.totalamountout + wp.currentvalue - wp.totalinvestedamount) >= %s
            {category_clause}
        """.format(category_clause=categoryClause)
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                result = cursor.fetchone()
                return result[0] if result else 0
                
        except Exception as e:
            logger.exception("%s :: Wallet count query failed: %s", LOG_PREFIX, str(e))
            return 0

