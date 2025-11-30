"""
Handler for persisting positions to database.
"""
from typing import Dict, List, Set
from decimal import Decimal
from django.utils import timezone

from positions.models import Position as PositionModel
from positions.enums.PositionStatus import PositionStatus
from positions.enums.TradeStatus import TradeStatus
from positions.enums.PositionUpdateType import PositionUpdateType
from positions.pojos.PolymarketPositionResponse import PolymarketPositionResponse
from positions.pojos.PositionUpdateStats import PositionUpdateResult
from positions.pojos.PositionUpdateStatus import PositionUpdateStatus
from positions.pojos.Position import Position as PositionPojo
from wallets.models import Wallet
from markets.models import Market
from events.pojos.Event import Event


class PositionPersistenceHandler:
    @staticmethod
    def persistNewPositions(wallet: Wallet, eventPojos: Dict[str, Event], marketLookup: Dict[str, Market]) -> None:
        if not eventPojos or not marketLookup:
            return
        
        positionObjects = []
        for eventPojo in eventPojos.values():
            for conditionId, marketPojo in eventPojo.markets.items():
                if conditionId in marketLookup:
                    for positionPojo in marketPojo.positions:
                        positionObjects.append(PositionModel(
                            walletsid=wallet,
                            marketsid=marketLookup[conditionId],
                            conditionid=conditionId,
                            outcome=positionPojo.outcome,
                            oppositeoutcome=positionPojo.oppositeOutcome,
                            title=positionPojo.title,
                            positionstatus=PositionStatus.OPEN.value if positionPojo.isOpen else PositionStatus.CLOSED.value,
                            tradestatus=TradeStatus.NEED_TO_PULL_TRADES.value if positionPojo.isOpen else TradeStatus.POSITION_CLOSED.value,
                            totalshares=positionPojo.totalShares,
                            currentshares=positionPojo.currentShares,
                            averageentryprice=positionPojo.averageEntryPrice,
                            amountspent=positionPojo.amountSpent,
                            amountremaining=positionPojo.amountRemaining,
                            calculatedamountinvested=Decimal('0'),
                            calculatedcurrentvalue=Decimal('0'),
                            calculatedamountout=Decimal('0'),
                            realizedpnl=Decimal('0'),
                            unrealizedpnl=Decimal('0'),
                            apirealizedpnl=positionPojo.apiRealizedPnl,
                            enddate=positionPojo.endDate,
                            negativerisk=positionPojo.negativeRisk
                        ))
        
        if positionObjects:
            PositionModel.objects.bulk_create(
                positionObjects,
                update_conflicts=True,
                update_fields=[
                    'positionstatus', 'tradestatus', 'totalshares', 'currentshares',
                    'averageentryprice', 'amountspent', 'amountremaining', 
                    'apirealizedpnl', 'enddate', 'negativerisk'
                ],
                unique_fields=['walletsid', 'marketsid', 'outcome'],
                batch_size=500
            )

    @staticmethod
    def updatePositionsForWallet(walletId: int, apiOpenPositions: List[PolymarketPositionResponse]) -> PositionUpdateResult:
        """
        Update all positions for a wallet efficiently with single API fetch, single DB fetch, and single bulk update.
        
        FOUR UPDATE CASES HANDLED:
        
        CASE 1: Position exists in API AND exists as OPEN in DB
        → Check if values changed (shares, price, current value)
        → If changed: Update position fields + Set tradestatus = NEED_TO_PULL_TRADES
        → If unchanged: Skip (no update needed)
        
        CASE 2: Position does NOT exist in API BUT exists as OPEN in DB  
        → Position was recently closed on platform
        → Set tradestatus = POSITION_CLOSED_NEED_DATA (triggers closed position API fetch later)
        → Keep position as OPEN status for now (will be updated when closed data is fetched)
        
        CASE 3: Position exists in API BUT exists as CLOSED in DB
        → Position was reopened on platform (user bought back into same market/outcome)
        → Update position fields from API + Set positionstatus = OPEN + Set tradestatus = NEED_TO_PULL_TRADES
        → This handles the rare case where user exits and re-enters same position
        
        CASE 4: Position exists in API BUT does NOT exist in DB (neither open nor closed)
        → New position entered by wallet
        → Create new position record + Set tradestatus = NEED_TO_PULL_TRADES
        → Requires market lookup/creation if market doesn't exist
        """
        # Fetch current open positions once
        currentOpenPositions = list(PositionModel.objects.filter(
            walletsid=walletId,
            positionstatus=PositionStatus.OPEN
        ).select_related('marketsid'))
        
        # Create lookup maps
        apiPositionMap = PositionPersistenceHandler._createAPIPositionMap(apiOpenPositions)
        dbOpenPositionMap = PositionPersistenceHandler._createDBPositionMap(currentOpenPositions)
        
        result = PositionUpdateResult()
        positionsToUpdate = []
        
        # Case 1: Update existing open positions
        result.updated = PositionPersistenceHandler.processExsistingOpenPositions(
            dbOpenPositionMap, apiPositionMap, positionsToUpdate
        )
        
        # Case 2: Mark positions as closed
        result.markedClosed = PositionPersistenceHandler.processClosedPositions(
            dbOpenPositionMap, apiPositionMap, positionsToUpdate
        )
        
        # Case 3 & 4: Handle positions in API but not in current open positions
        apiKeysNotInOpen = set(apiPositionMap.keys()) - set(dbOpenPositionMap.keys())
        if apiKeysNotInOpen:
            result.reopened = PositionPersistenceHandler.processReopenedPositions(
                walletId, apiKeysNotInOpen, apiPositionMap, positionsToUpdate
            )
            
            result.created = PositionPersistenceHandler.processNewPositions(
                walletId, apiKeysNotInOpen, apiPositionMap
            )
        
        # Single bulk update at the end
        if positionsToUpdate:
            PositionPersistenceHandler._bulkUpdatePositions(positionsToUpdate)
        
        return result

    @staticmethod
    def processExsistingOpenPositions(dbOpenPositionMap: Dict[str, PositionModel], 
                                apiPositionMap: Dict[str, PolymarketPositionResponse],
                                positionsToUpdate: List[PositionModel]) -> int:
        """
        Case 1: Position in API + Open in DB → Smart update based on change type
        """
        updatedCount = 0
        
        for key, dbPosition in dbOpenPositionMap.items():
            if key in apiPositionMap:
                apiPosition = apiPositionMap[key]
                
                # Analyze what type of change occurred
                updateStatus = PositionPersistenceHandler.analyzePositionChanges(dbPosition, apiPosition)
                
                # Update position values from API
                PositionPersistenceHandler.updatePositionsFromAPI(dbPosition, apiPosition)
                
                # Set trade status based on change type
                if updateStatus.targetTradeStatus:
                    dbPosition.tradestatus = updateStatus.targetTradeStatus
                # If targetTradeStatus is None, preserve existing trade status
                
                dbPosition.lastupdatedat = timezone.now()
                positionsToUpdate.append(dbPosition)
                updatedCount += 1
        
        return updatedCount

    @staticmethod
    def processClosedPositions(dbOpenPositionMap: Dict[str, PositionModel],
                              apiPositionMap: Dict[str, PolymarketPositionResponse],
                              positionsToUpdate: List[PositionModel]) -> int:
        """
        Case 2: Position not in API + Open in DB → Set POSITION_CLOSED_NEED_DATA
        """
        # Efficiently find positions that are closed (in DB but not in API)
        closedPositionKeys = set(dbOpenPositionMap.keys()) - set(apiPositionMap.keys())
        
        # Only iterate over positions that are actually closed
        for key in closedPositionKeys:
            dbPosition = dbOpenPositionMap[key]
            dbPosition.tradestatus = TradeStatus.POSITION_CLOSED_NEED_DATA
            dbPosition.lastupdatedat = timezone.now()
            positionsToUpdate.append(dbPosition)
        
        return len(closedPositionKeys)

    @staticmethod
    def processReopenedPositions(walletId: int, 
                                apiKeysNotInOpen: Set[str],
                                apiPositionMap: Dict[str, PolymarketPositionResponse],
                                positionsToUpdate: List[PositionModel]) -> int:
        """
        Case 3: Position in API + Closed in DB → Reopen, set NEED_TO_PULL_TRADES
        """
        if not apiKeysNotInOpen:
            return 0
            
        # Only fetch closed positions if we have potential reopenings
        closedPositions = list(PositionModel.objects.filter(
            walletsid=walletId,
            positionstatus=PositionStatus.CLOSED
        ))
        
        closedPositionMap = PositionPersistenceHandler._createDBPositionMap(closedPositions)
        reopenedCount = 0
        
        for key in apiKeysNotInOpen:
            if key in closedPositionMap:
                closedPosition = closedPositionMap[key]
                apiPosition = apiPositionMap[key]
                
                # Update closed position to open status
                PositionPersistenceHandler.updatePositionsFromAPI(closedPosition, apiPosition)
                closedPosition.positionstatus = PositionStatus.OPEN
                closedPosition.tradestatus = TradeStatus.NEED_TO_PULL_TRADES
                closedPosition.lastupdatedat = timezone.now()
                positionsToUpdate.append(closedPosition)
                reopenedCount += 1
        
        return reopenedCount

    @staticmethod
    def processNewPositions(walletId: int,
                           apiKeysNotInOpen: Set[str], 
                           apiPositionMap: Dict[str, PolymarketPositionResponse]) -> int:
        """
        Case 4: Position in API but does NOT exist in DB → Create new position
        Follows exact same pattern as FetchNewWalletPositionsScheduler
        """
        if not apiKeysNotInOpen:
            return 0
            
        # Find positions that don't exist in database at all
        allExistingPositions = list(PositionModel.objects.filter(walletsid=walletId))
        existingPositionMap = PositionPersistenceHandler._createDBPositionMap(allExistingPositions)
        
        newPositionKeys = [key for key in apiKeysNotInOpen if key not in existingPositionMap]
        
        if not newPositionKeys:
            return 0
        
        # Extract new API positions
        newApiPositions = [apiPositionMap[key] for key in newPositionKeys]
        
        # Follow exact FetchNewWalletPositionsScheduler pattern:
        # 1. buildEvent() - converts API positions to Event POJOs
        # 2. persistEvent() - handles Event→Market→Position creation
        from positions.schedulers.FetchNewWalletPositionsScheduler import FetchNewWalletPositionsScheduler
        scheduler = FetchNewWalletPositionsScheduler()
        
        newEvents = scheduler.buildEvent(newApiPositions)
        
        if newEvents:
            wallet = Wallet.objects.get(walletsid=walletId)
            scheduler.persistEvent(wallet, newEvents)
        
        return len(newPositionKeys)

    @staticmethod
    def _createAPIPositionMap(openPositions: List[PolymarketPositionResponse]) -> Dict[str, PolymarketPositionResponse]:
        """Create lookup map: conditionId+outcome -> PolymarketPositionResponse"""
        apiMap = {}
        for position in openPositions:
            key = f"{position.conditionId}_{position.outcome}"
            apiMap[key] = position
        return apiMap

    @staticmethod
    def _createDBPositionMap(dbPositions: List[PositionModel]) -> Dict[str, PositionModel]:
        """Create lookup map: conditionId+outcome -> Position model"""
        dbMap = {}
        for position in dbPositions:
            key = f"{position.conditionid}_{position.outcome}"
            dbMap[key] = position
        return dbMap

    @staticmethod
    def analyzePositionChanges(dbPosition: PositionModel, apiPosition: PolymarketPositionResponse) -> PositionUpdateStatus:
        """
        Simple analysis: check if totalBought changed.
        
        If totalBought changed: Update position + set NEED_TO_PULL_TRADES
        If no change in totalBought: Just update position values
        """
        # Check if totalBought changed (indicates new trades)
        totalBoughtChanged = abs(float(dbPosition.totalshares) - float(apiPosition.totalBought or 0)) > 0.000001
        
        if totalBoughtChanged:
            return PositionUpdateStatus.forTradeActivity()
        else:
            return PositionUpdateStatus.forPriceUpdate()
    
    @staticmethod
    def needsUpdate(dbPosition: PositionModel, apiPosition: PolymarketPositionResponse) -> bool:
        """Check if position needs any update."""
        from positions.enums.PositionUpdateType import PositionUpdateType
        updateStatus = PositionPersistenceHandler.analyzePositionChanges(dbPosition, apiPosition)
        return updateStatus.updateType != PositionUpdateType.NO_CHANGE

    @staticmethod  
    def updatePositionsFromAPI(dbPosition: PositionModel, apiPosition: PolymarketPositionResponse) -> None:
        dbPosition.totalshares = Decimal(str(apiPosition.size or 0))
        dbPosition.currentshares = Decimal(str(apiPosition.size or 0))
        dbPosition.averageentryprice = Decimal(str(apiPosition.avgPrice or 0))
        dbPosition.amountspent = Decimal(str(apiPosition.totalBought or 0)) * Decimal(str(apiPosition.avgPrice or 0))
        dbPosition.amountremaining = Decimal(str(apiPosition.currentValue or 0))

    @staticmethod
    def _bulkUpdatePositions(positionsToUpdate: List[PositionModel]) -> None:
        """Perform bulk update on positions"""
        PositionModel.objects.bulk_update(
            positionsToUpdate,
            [
                'positionstatus', 'totalshares', 'currentshares', 'averageentryprice',
                'amountspent', 'amountremaining', 'apirealizedpnl', 'tradestatus', 'lastupdatedat'
            ],
            batch_size=500
        )

    @staticmethod
    def getRecentlyClosedPosition() -> Dict[str, tuple]:
        """
        Retrieve positions with OPEN status and POSITION_CLOSED_TRADES_SYNCED trade status.
        Joins Position and Wallet tables to fetch required data efficiently.
        
        Returns:
            Dict mapping "proxywallet_conditionid_outcome" -> (positionId, PositionPojo)
            Example: "0xabc123_0xdef456_Yes" -> (123, PositionPojo(...))
        """
        from django.db import connection
        
        query = """
            SELECT 
                p.positionid,
                w.proxywallet,
                p.conditionid,
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
                p.negativerisk
            FROM positions p
            INNER JOIN wallets w ON p.walletsid = w.walletsid
            WHERE p.positionstatus = %s 
            AND p.tradestatus = %s
        """
        
        positionMap = {}
        
        with connection.cursor() as cursor:
            cursor.execute(query, [
                PositionStatus.OPEN.value,
                TradeStatus.POSITION_CLOSED_TRADES_SYNCED.value
            ])
            
            for row in cursor.fetchall():
                positionId = row[0]
                proxyWallet = row[1]
                conditionId = row[2]
                outcome = row[3]
                
                # Construct map key: proxywallet_conditionid_outcome
                mapKey = f"{proxyWallet}_{conditionId}_{outcome}"
                
                # Create Position POJO from database row
                positionPojo = PositionPojo(
                    outcome=outcome,
                    oppositeOutcome=row[4] or '',
                    title=row[5] or '',
                    totalShares=Decimal(str(row[6] or 0)),
                    currentShares=Decimal(str(row[7] or 0)),
                    averageEntryPrice=Decimal(str(row[8] or 0)),
                    amountSpent=Decimal(str(row[9] or 0)),
                    amountRemaining=Decimal(str(row[10] or 0)),
                    apiRealizedPnl=Decimal(str(row[11])) if row[11] is not None else None,
                    endDate=row[12],
                    negativeRisk=bool(row[13]) if row[13] is not None else False,
                    isOpen=True  # Always True since we filter for OPEN status
                )
                
                positionMap[mapKey] = (positionId, positionPojo)
        
        return positionMap

    @staticmethod
    def bulkUpdateClosedPositions(positionUpdates: List[tuple]) -> int:
        """
        Bulk update positions with closed position data from Position POJOs.
        
        Args:
            positionUpdates: List of (positionId, PositionPojo) tuples
            
        Returns:
            Number of positions updated
        """
        if not positionUpdates:
            return 0
        
        positionIds = [positionId for positionId, _ in positionUpdates]
        positions = PositionModel.objects.filter(positionid__in=positionIds)
        
        positionsToUpdate = []
        updateMap = {positionId: positionPojo for positionId, positionPojo in positionUpdates}
        
        for position in positions:
            if position.positionid in updateMap:
                positionPojo = updateMap[position.positionid]
                
                # Update position fields directly from POJO
                position.totalshares = positionPojo.totalShares
                position.currentshares = positionPojo.currentShares
                position.averageentryprice = positionPojo.averageEntryPrice
                position.amountspent = positionPojo.amountSpent
                position.amountremaining = positionPojo.amountRemaining
                position.apirealizedpnl = positionPojo.apiRealizedPnl if positionPojo.apiRealizedPnl else Decimal('0')
                
                # Set final closed status
                position.positionstatus = PositionStatus.CLOSED.value
                position.tradestatus = TradeStatus.TRADES_SYNCED.value
                position.lastupdatedat = timezone.now()
                
                positionsToUpdate.append(position)
        
        if positionsToUpdate:
            PositionPersistenceHandler._bulkUpdatePositions(positionsToUpdate)
        
        return len(positionsToUpdate)
