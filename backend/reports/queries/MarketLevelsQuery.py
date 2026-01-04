"""
SQL Query for Market Levels Report.

Fetches all open positions for a specific market with their entry prices.
Optimized for single market lookup with minimal data transfer.
"""
import logging
from typing import List, Dict
from django.db import connection

from reports.Constants import LOG_PREFIX_MARKET_LEVELS as LOG_PREFIX

logger = logging.getLogger(__name__)


class MarketLevelsQuery:
    """
    Executes SQL query to fetch position data for a specific market.
    
    Returns position-level data including:
    - Wallet ID
    - Outcome
    - Average entry price
    - Amount spent
    """
    
    @staticmethod
    def execute(marketId: int) -> List[Dict]:
        query = """
            SELECT 
                p.positionid,
                p.walletsid,
                p.marketsid,
                p.outcome,
                p.averageentryprice,
                p.amountspent,
                p.positionstatus,
                p.conditionid,
                m.marketslug,
                m.question
            FROM positions p
            INNER JOIN markets m ON p.marketsid = m.marketsid
            WHERE p.marketsid = %s
            AND p.positionstatus = 1
            AND p.enddate > NOW()
            ORDER BY p.outcome, p.averageentryprice
        """
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, [marketId])
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            logger.info("%s :: Query executed | MarketId: %d | Positions: %d",
                LOG_PREFIX, marketId, len(results)
            )
            
            return results
            
        except Exception as e:
            logger.info("%s :: Query failed | MarketId: %d | Error: %s",
                LOG_PREFIX, marketId, str(e)
            )
            raise
    
    @staticmethod
    def getMarketInfo(marketId: int) -> Dict:
        """
        Get basic market information.
        
        Args:
            marketId: The market ID
            
        Returns:
            Dictionary with market info or empty dict if not found
        """
        query = """
            SELECT 
                m.marketsid as marketid,
                m.marketslug,
                m.question,
                p.conditionid
            FROM markets m
            LEFT JOIN positions p ON p.marketsid = m.marketsid AND p.positionstatus = 1
            WHERE m.marketsid = %s
            LIMIT 1
        """
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, [marketId])
                row = cursor.fetchone()
                
                if row:
                    columns = [col[0] for col in cursor.description]
                    return dict(zip(columns, row))
                return {}
                
        except Exception as e:
            logger.exception(
                "%s :: Market info query failed | MarketId: %d | Error: %s",
                LOG_PREFIX, marketId, str(e)
            )
            return {}

