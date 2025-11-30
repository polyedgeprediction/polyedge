"""
DB Handler for trade processing operations.
Returns proper nested POJO structures matching the existing architecture.
"""
from typing import List, Dict, Optional
from django.db import connection
import logging

from positions.models import Position as PositionModel
from positions.enums.TradeStatus import TradeStatus
from trades.models import Batch as BatchModel
from trades.pojos.Batch import Batch
from markets.pojos.Market import Market
from positions.pojos.Position import Position
from wallets.pojos.WalletWithMarkets import WalletWithMarkets

logger = logging.getLogger(__name__)


class TradePersistenceHandler:
    """
    Database handler for trade processing operations.
    Returns proper nested POJO structures for wallet-market combinations.
    """
    
    @staticmethod
    def getWalletsWithMarketsNeedingTradeSync() -> List[WalletWithMarkets]:
        """
        Get wallets with their markets that need trade synchronization.
        Returns proper nested POJO structure: Wallet → Markets → Positions + Batch.
        Single optimized JOIN query to get all data at once.
        
        Returns:
            List of WalletWithMarkets objects with nested structure
        """
        try:
            # Single query to get all data: wallets, batches, and positions
            query = """
            SELECT 
                p.walletsid as wallet_id,
                p.marketsid as market_id, 
                p.conditionid,
                w.proxywallet,
                w.username,
                b.batchid as batch_id,
                b.latestfetchedtime as latest_fetched_time,
                b.isactive as batch_is_active,
                p.outcome,
                p.oppositeoutcome,
                p.title,
                p.totalshares,
                p.currentshares,
                p.averageentryprice,
                p.amountspent,
                p.amountremaining,
                p.apirealizedpnl,
                p.enddate,
                p.negativerisk,
                p.positionstatus
            FROM positions p
            INNER JOIN wallets w ON p.walletsid = w.walletsid
            LEFT JOIN batches b ON p.walletsid = b.walletsid AND p.marketsid = b.marketsid
            WHERE p.tradestatus = %s
            ORDER BY p.walletsid, p.marketsid, p.outcome
            """
            
            with connection.cursor() as cursor:
                cursor.execute(query, [TradeStatus.NEED_TO_PULL_TRADES.value])
                rows = cursor.fetchall()
            
            # Group data by wallet and build nested structure without duplicates
            walletsData = {}
            
            for row in rows:
                walletId = row[0]
                marketId = row[1]
                conditionId = row[2]
                proxyWallet = row[3]
                username = row[4]
                batchId = row[5]
                latestFetchedTime = row[6]
                batchIsActive = row[7]
                outcome = row[8]
                oppositeOutcome = row[9]
                title = row[10]
                totalShares = row[11]
                currentShares = row[12]
                averageEntryPrice = row[13]
                amountSpent = row[14]
                amountRemaining = row[15]
                apiRealizedPnl = row[16]
                endDate = row[17]
                negativeRisk = row[18]
                positionStatus = row[19]
                
                # Get or create wallet POJO
                if walletId not in walletsData:
                    walletsData[walletId] = WalletWithMarkets(
                        walletId=walletId,
                        proxyWallet=proxyWallet,
                        username=username or ""
                    )
                
                wallet = walletsData[walletId]
                
                # Get or create market POJO
                if conditionId not in wallet.markets:
                    market = Market(
                        conditionId=conditionId,
                        marketSlug="",  # Will be populated when needed
                        question="",    # Will be populated when needed
                        endDate=None,   # Will be populated when needed
                        isOpen=True,    # Default for positions needing sync
                        marketPk=marketId  # Store database primary key for efficient persistence
                    )
                    
                    # Add batch information if exists
                    if batchId:
                        batch = Batch(
                            walletId=walletId,
                            marketId=marketId,
                            latestFetchedTime=latestFetchedTime,
                            isActive=bool(batchIsActive),
                            batchId=batchId
                        )
                        market.setBatch(batch)
                    
                    wallet.addMarket(market)
                
                # Add position to market
                market = wallet.getMarket(conditionId)
                if market:
                    from positions.enums.PositionStatus import PositionStatus
                    isOpen = positionStatus == PositionStatus.OPEN.value
                    
                    position = Position(
                        outcome=outcome,
                        oppositeOutcome=oppositeOutcome,
                        title=title,
                        totalShares=totalShares,
                        currentShares=currentShares,
                        averageEntryPrice=averageEntryPrice,
                        amountSpent=amountSpent,
                        amountRemaining=amountRemaining,
                        apiRealizedPnl=apiRealizedPnl,
                        endDate=endDate,
                        negativeRisk=negativeRisk,
                        isOpen=isOpen
                    )
                    market.addPosition(position)
            
            walletList = list(walletsData.values())
            return walletList
            
        except Exception as e:
            logger.error(f"FETCH_TRADES_SCHEDULER :: Failed to get wallets with markets needing sync: {e}")
            return []
    

    @staticmethod
    def updateBatchTimestamp(batch: Batch, latestTimestamp: int) -> bool:
        """
        Update the latest fetched timestamp for a batch.
        
        Args:
            batch: Batch POJO with batchId
            latestTimestamp: Unix timestamp of latest trade processed
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not batch.batchId:
                logger.warning(f"TRADE_SYNC :: Cannot update batch without ID: {batch}")
                return False
            
            from django.utils import timezone as django_timezone
            
            # Store epoch timestamp directly
            updated = BatchModel.objects.filter(batchid=batch.batchId).update(
                latestfetchedtime=latestTimestamp,
                lastupdatedat=django_timezone.now()
            )
            
            if updated > 0:
                # Update POJO as well
                batch.latestFetchedTime = latestTimestamp
                logger.debug(f"TRADE_SYNC :: Updated batch {batch.batchId} timestamp to {latestTimestamp}")
                return True
            else:
                logger.warning(f"TRADE_SYNC :: No batch found with ID {batch.batchId}")
                return False
            
        except Exception as e:
            logger.error(f"TRADE_SYNC :: Failed to update batch timestamp: {e}")
            return False
    
    @staticmethod
    def bulkUpdatePositionsTradeStatus(statusUpdates: List[Dict]) -> int:
        """
        Bulk update trade status for multiple wallet-market combinations.
        Much more efficient than individual updates.
        
        Args:
            statusUpdates: List of dicts with walletId, conditionId, status
            
        Returns:
            Number of positions successfully updated
        """
        try:
            from django.utils import timezone as django_timezone
            from django.db import connection
            
            if not statusUpdates:
                return 0
            
            # Build bulk update query
            updates = []
            params = []
            
            for update in statusUpdates:
                updates.append("(walletsid = %s AND conditionid = %s)")
                params.extend([update['walletId'], update['conditionId']])
            
            # Use CASE statement for bulk update with different statuses
            caseStatements = []
            for update in statusUpdates:
                caseStatements.append(f"WHEN (walletsid = %s AND conditionid = %s) THEN %s")
                params.extend([update['walletId'], update['conditionId'], update['status'].value])
            
            query = f"""
                UPDATE positions 
                SET tradestatus = CASE 
                    {' '.join(caseStatements)}
                    ELSE tradestatus 
                END,
                lastupdatedat = %s
                WHERE ({' OR '.join(updates)})
            """
            
            params.append(django_timezone.now())
            
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                updated = cursor.rowcount
            
            logger.info(f"TRADE_SYNC :: Bulk updated {updated} positions for {len(statusUpdates)} markets")
            return updated
            
        except Exception as e:
            logger.error(f"TRADE_SYNC :: Failed to bulk update positions: {e}")
            return 0
    
    @staticmethod
    def bulkPersistAggregatedTrades(tradeDataList: List[Dict]) -> int:
        try:
            from django.db import connection
            from django.utils import timezone as django_timezone
            
            if not tradeDataList:
                return 0
            
            # Build bulk INSERT query with direct marketPk usage - NO LOOKUP NEEDED!
            values = []
            params = []
            
            for tradeData in tradeDataList:
                trade = tradeData['trade']  # AggregatedTrade POJO
                walletId = tradeData['walletId']
                marketPk = tradeData['marketPk']  # Direct primary key from Market POJO
                
                if not marketPk:
                    logger.warning(f"FETCH_TRADES_SCHEDULER :: No marketPk for conditionId {trade.conditionId}, skipping trade")
                    continue
                
                values.append("(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
                params.extend([
                    walletId,           # walletsid (FK)
                    marketPk,           # marketsid (FK) - direct primary key, no lookup!
                    trade.conditionId,  # conditionid 
                    trade.tradeType.value,  # tradetype
                    trade.outcome,      # outcome
                    float(trade.totalShares),  # totalshares
                    float(trade.totalAmount),  # totalamount
                    trade.tradeDate,    # tradedate
                    trade.transactionCount,  # transactioncount
                    django_timezone.now(),  # createdat
                    django_timezone.now()   # lastupdatedat
                ])
            
            if not values:
                logger.warning("FETCH_TRADES_SCHEDULER :: No valid trades to persist")
                return 0
            
            query = f"""
                INSERT INTO trades 
                (walletsid, marketsid, conditionid, tradetype, outcome, 
                 totalshares, totalamount, tradedate, transactioncount, createdat, lastupdatedat)
                VALUES {', '.join(values)}
            """
            
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                inserted = cursor.rowcount
            
            logger.info(f"FETCH_TRADES_SCHEDULER :: Bulk persisted {inserted} aggregated trades")
            return inserted
            
        except Exception as e:
            logger.error(f"FETCH_TRADES_SCHEDULER :: Failed to bulk persist aggregated trades: {e}")
            return 0
    
    
    @staticmethod
    def bulkUpdateBatchTimestamps(batchUpdates: List[Dict]) -> int:
        """
        Highly optimized bulk update of batch timestamps using efficient CASE statement.
        Uses optimal indexing on batchid for maximum performance.
        
        Args:
            batchUpdates: List of dicts with batchId and timestamp
            
        Returns:
            Number of batches successfully updated
        """
        try:
            from django.db import connection
            from django.utils import timezone as django_timezone
            from datetime import datetime, timezone
            
            if not batchUpdates:
                return 0
            
            # Optimized approach: Single UPDATE with CASE statement for maximum efficiency
            caseStatements = []
            params = []
            batchIds = []
            
            for update in batchUpdates:
                caseStatements.append("WHEN batchid = %s THEN %s")
                latestDatetime = datetime.fromtimestamp(update['timestamp'], tz=timezone.utc)
                params.extend([update['batchId'], latestDatetime])
                batchIds.append(update['batchId'])
            
            # Optimized query with indexed WHERE clause
            query = f"""
                UPDATE batches 
                SET latestfetchedtime = CASE 
                    {' '.join(caseStatements)}
                    ELSE latestfetchedtime 
                END,
                lastupdatedat = %s
                WHERE batchid IN ({','.join(['%s'] * len(batchIds))})
            """
            
            params.append(django_timezone.now())
            params.extend(batchIds)
            
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                updated = cursor.rowcount
            
            logger.debug(f"TRADE_SYNC :: Bulk updated {updated} batch timestamps")
            return updated
            
        except Exception as e:
            logger.error(f"TRADE_SYNC :: Failed to bulk update batch timestamps: {e}")
            return 0
    
    @staticmethod  
    def bulkUpdateStatusAndTimestamps(statusUpdates: List[Dict], batchUpdates: List[Dict]) -> tuple[int, int]:
        try:
            from django.db import connection
            from django.utils import timezone as django_timezone
            
            positionsUpdated = 0
            batchesUpdated = 0
            
            with connection.cursor() as cursor:
                # Execute position updates first (most critical operation)
                if statusUpdates:
                    positionsUpdated = TradePersistenceHandler._executeBulkPositionUpdates(
                        cursor, statusUpdates, django_timezone.now()
                    )
                
                # Execute batch updates second (timestamp tracking)
                if batchUpdates:
                    batchesUpdated = TradePersistenceHandler._executeBulkBatchUpdates(
                        cursor, batchUpdates, django_timezone.now()
                    )
            
            logger.info(
                f"FETCH_TRADES_SCHEDULER :: Optimized bulk updates completed | "
                f"Positions: {positionsUpdated}, Batches: {batchesUpdated}"
            )
            
            return positionsUpdated, batchesUpdated
            
        except Exception as e:
            logger.error(f"FETCH_TRADES_SCHEDULER :: Failed to execute optimized bulk updates: {e}")
            return 0, 0
    
    @staticmethod
    def _executeBulkPositionUpdates(cursor, statusUpdates: List[Dict], updateTime) -> int:
        """Execute optimized position status updates with single query."""
        if not statusUpdates:
            return 0
        
        # Build optimized bulk update with CASE statement
        caseStatements = []
        params = []
        conditions = []
        
        for update in statusUpdates:
            caseStatements.append("WHEN (walletsid = %s AND conditionid = %s) THEN %s")
            params.extend([update['walletId'], update['conditionId'], update['status'].value])
            conditions.append("(walletsid = %s AND conditionid = %s)")
        
        # Add condition parameters
        conditionParams = []
        for update in statusUpdates:
            conditionParams.extend([update['walletId'], update['conditionId']])
        
        query = f"""
            UPDATE positions 
            SET tradestatus = CASE 
                {' '.join(caseStatements)}
                ELSE tradestatus 
            END,
            lastupdatedat = %s
            WHERE ({' OR '.join(conditions)})
        """
        
        allParams = params + [updateTime] + conditionParams
        cursor.execute(query, allParams)
        return cursor.rowcount
    
    @staticmethod
    def _executeBulkBatchUpdates(cursor, batchUpdates: List[Dict], updateTime) -> int:
        """Execute optimized batch timestamp updates with single query."""
        if not batchUpdates:
            return 0
        
        # Build optimized bulk update with CASE statement  
        caseStatements = []
        params = []
        batchIds = []
        
        for update in batchUpdates:
            caseStatements.append("WHEN batchid = %s THEN %s")
            # Store epoch timestamp directly
            params.extend([update['batchId'], update['timestamp']])
            batchIds.append(update['batchId'])
        
        query = f"""
            UPDATE batches 
            SET latestfetchedtime = CASE 
                {' '.join(caseStatements)}
                ELSE latestfetchedtime 
            END,
            lastupdatedat = %s
            WHERE batchid IN ({','.join(['%s'] * len(batchIds))})
        """
        
        allParams = params + [updateTime] + batchIds
        cursor.execute(query, allParams)
        return cursor.rowcount
    
    @staticmethod
    def bulkUpdatePNL(filterStatus: TradeStatus, finalStatus: TradeStatus) -> int:
        """
        Calculate PNL for positions with specified status using optimized CTE approach.
        
        Performs atomic financial calculation by:
        1. Aggregating trade amounts by wallet-market combination
        2. Calculating invested amount (negative totalamount values)
        3. Calculating amount out (positive totalamount values)  
        4. Computing realized PNL as difference
        5. Updating positions and marking with final status
        
        Args:
            filterStatus: Status to filter positions for PNL calculation
            finalStatus: Status to set after PNL calculation is complete
        
        Returns:
            Number of positions successfully updated with PNL calculations
        """
        try:
            from django.db import connection
            from django.utils import timezone as django_timezone

            logger.info(f"FETCH_TRADES_SCHEDULER :: Calculating PNL for positions marked for calculation")
            
            # Optimized CTE-based query for atomic PNL calculation
            query = """
                WITH trade_aggregates AS (
                    SELECT 
                        t.walletsid,
                        t.conditionid,
                        SUM(CASE WHEN t.totalamount < 0 THEN ABS(t.totalamount) ELSE 0 END) AS total_invested,
                        SUM(CASE WHEN t.totalamount >= 0 THEN t.totalamount ELSE 0 END) AS total_out
                    FROM trades t
                    INNER JOIN positions p ON 
                        t.walletsid = p.walletsid 
                        AND t.conditionid = p.conditionid 
                    WHERE p.tradestatus = %s
                    GROUP BY t.walletsid, t.conditionid
                )
                UPDATE positions 
                SET 
                    calculatedamountinvested = ta.total_invested,
                    calculatedamountout = ta.total_out,
                    realizedpnl = ta.total_out - ta.total_invested,
                    tradestatus = %s,
                    lastupdatedat = %s
                FROM trade_aggregates ta
                WHERE 
                    positions.walletsid = ta.walletsid 
                    AND positions.conditionid = ta.conditionid 
            """
            
            with connection.cursor() as cursor:
                cursor.execute(query, [
                    filterStatus.value,  # Filter condition
                    finalStatus.value,   # New status
                    django_timezone.now()
                ])
                
                updated = cursor.rowcount
            
            logger.info(f"FETCH_TRADES_SCHEDULER :: Calculated PNL for {updated} positions")
            return updated
            
        except Exception as e:
            logger.error(f"FETCH_TRADES_SCHEDULER :: Failed to calculate position PNL: {e}")
            return 0


    @staticmethod
    def getWalletsWithMarketsForClosedPositions() -> List[WalletWithMarkets]:
        """
        Get wallets with their markets for closed positions.
        Returns proper nested POJO structure: Wallet → Markets → Positions + Batch.
        """
        try:
            query = """
            SELECT 
                p.walletsid as wallet_id,
                p.marketsid as market_id, 
                p.conditionid,
                w.proxywallet,
                w.username,
                b.batchid as batch_id,
                b.latestfetchedtime as latest_fetched_time,
                b.isactive as batch_is_active,
                p.outcome,
                p.oppositeoutcome,
                p.title,
                p.totalshares,
                p.currentshares,
                p.averageentryprice,
                p.amountspent,
                p.amountremaining,
                p.apirealizedpnl,
                p.enddate,
                p.negativerisk,
                p.positionstatus
            FROM positions p
            INNER JOIN wallets w ON p.walletsid = w.walletsid
            LEFT JOIN batches b ON p.walletsid = b.walletsid AND p.marketsid = b.marketsid
            WHERE p.tradestatus = %s
            ORDER BY p.walletsid, p.marketsid, p.outcome
            """
            
            with connection.cursor() as cursor:
                cursor.execute(query, [TradeStatus.POSITION_CLOSED_NEED_DATA.value])
                rows = cursor.fetchall()
            
            # Group data by wallet and build nested structure without duplicates
            walletsData = {}
            
            for row in rows:
                walletId = row[0]
                marketId = row[1]
                conditionId = row[2]
                proxyWallet = row[3]
                username = row[4]
                batchId = row[5]
                latestFetchedTime = row[6]
                batchIsActive = row[7]
                outcome = row[8]
                oppositeOutcome = row[9]
                title = row[10]
                totalShares = row[11]
                currentShares = row[12]
                averageEntryPrice = row[13]
                amountSpent = row[14]
                amountRemaining = row[15]
                apiRealizedPnl = row[16]
                endDate = row[17]
                negativeRisk = row[18]
                positionStatus = row[19]
                
                # Get or create wallet POJO
                if walletId not in walletsData:
                    walletsData[walletId] = WalletWithMarkets(
                        walletId=walletId,
                        proxyWallet=proxyWallet,
                        username=username or ""
                    )
                
                wallet = walletsData[walletId]
                
                # Get or create market POJO
                if conditionId not in wallet.markets:
                    market = Market(
                        conditionId=conditionId,
                        marketSlug="",  # Will be populated when needed
                        question="",    # Will be populated when needed
                        endDate=None,   # Will be populated when needed
                        isOpen=False,    # Default for closed positions
                        marketPk=marketId  # Store database primary key for efficient persistence
                    )
                    
                    # Add batch information if exists
                    if batchId:
                        batch = Batch(
                            walletId=walletId,
                            marketId=marketId,
                            latestFetchedTime=latestFetchedTime,
                            isActive=bool(batchIsActive),
                            batchId=batchId
                        )
                        market.setBatch(batch)
                    
                    wallet.addMarket(market)
                
                # Add position to market
                market = wallet.getMarket(conditionId)
                if market:
                    # Closed position
                    position = Position(
                        outcome=outcome,
                        oppositeOutcome=oppositeOutcome,
                        title=title,
                        totalShares=totalShares,
                        currentShares=currentShares,
                        averageEntryPrice=averageEntryPrice,
                        amountSpent=amountSpent,
                        amountRemaining=amountRemaining,
                        apiRealizedPnl=apiRealizedPnl,
                        endDate=endDate,
                        negativeRisk=negativeRisk,
                        isOpen=False
                    )
                    market.addPosition(position)
            
            walletList = list(walletsData.values())
            return walletList
            
        except Exception as e:
            logger.error(f"RECENTLY_CLOSED_POSITIONS_SCHEDULER :: Failed to get wallets with markets needing sync: {e}")
            return []
    
