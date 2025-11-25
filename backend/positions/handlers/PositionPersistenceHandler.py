"""
Handler for persisting positions to database.
"""
from typing import Dict, List, Set
from decimal import Decimal
from django.utils import timezone

from positions.models import Position as PositionModel
from positions.enums.PositionStatus import PositionStatus
from positions.enums.TradeStatus import TradeStatus
from positions.pojos.PolymarketPositionResponse import PolymarketPositionResponse
from positions.pojos.PositionUpdateStats import PositionUpdateResult
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
        
        THREE UPDATE CASES HANDLED:
        
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
        
        EFFICIENCY DESIGN:
        • Single API fetch (passed as parameter)
        • Single DB query for open positions  
        • Single additional DB query for closed positions (only if Case 3 is needed)
        • Single bulk update for all changes
        
        Args:
            walletId: Database ID of the wallet
            apiOpenPositions: Pre-fetched list of open positions from API
            
        Returns:
            PositionUpdateResult with update statistics
        """
        # Fetch current open positions once
        currentOpenPositions = list(PositionModel.objects.filter(
            walletsid=walletId,
            positionstatus=PositionStatus.OPEN
        ).select_related('marketsid'))
        
        # Create lookup maps
        apiPositionMap = PositionPersistenceHandler._createApiPositionMap(apiOpenPositions)
        dbOpenPositionMap = PositionPersistenceHandler._createDbPositionMap(currentOpenPositions)
        
        result = PositionUpdateResult()
        positionsToUpdate = []
        
        # Case 1: Update existing open positions
        result.updated = PositionPersistenceHandler._processExistingPositions(
            dbOpenPositionMap, apiPositionMap, positionsToUpdate
        )
        
        # Case 2: Mark positions as closed
        result.markedClosed = PositionPersistenceHandler._processClosedPositions(
            dbOpenPositionMap, apiPositionMap, positionsToUpdate
        )
        
        # Case 3: Reopen closed positions (only if needed)
        apiKeysNotInOpen = set(apiPositionMap.keys()) - set(dbOpenPositionMap.keys())
        if apiKeysNotInOpen:
            result.reopened = PositionPersistenceHandler._processReopenedPositions(
                walletId, apiKeysNotInOpen, apiPositionMap, positionsToUpdate
            )
        
        # Single bulk update at the end
        if positionsToUpdate:
            PositionPersistenceHandler._bulkUpdatePositions(positionsToUpdate)
        
        return result

    @staticmethod
    def _processExistingPositions(dbOpenPositionMap: Dict[str, PositionModel], 
                                apiPositionMap: Dict[str, PolymarketPositionResponse],
                                positionsToUpdate: List[PositionModel]) -> int:
        """
        Case 1: Position in API + Open in DB → Update if changed, set NEED_TO_PULL_TRADES
        """
        updatedCount = 0
        
        for key, dbPosition in dbOpenPositionMap.items():
            if key in apiPositionMap:
                apiPosition = apiPositionMap[key]
                
                if PositionPersistenceHandler._needsUpdate(dbPosition, apiPosition):
                    PositionPersistenceHandler._updatePositionFromApi(dbPosition, apiPosition)
                    dbPosition.tradestatus = TradeStatus.NEED_TO_PULL_TRADES
                    dbPosition.lastupdatedat = timezone.now()
                    positionsToUpdate.append(dbPosition)
                    updatedCount += 1
        
        return updatedCount

    @staticmethod
    def _processClosedPositions(dbOpenPositionMap: Dict[str, PositionModel],
                              apiPositionMap: Dict[str, PolymarketPositionResponse],
                              positionsToUpdate: List[PositionModel]) -> int:
        """
        Case 2: Position not in API + Open in DB → Set POSITION_CLOSED_NEED_DATA
        """
        closedCount = 0
        
        for key, dbPosition in dbOpenPositionMap.items():
            if key not in apiPositionMap:
                dbPosition.tradestatus = TradeStatus.POSITION_CLOSED_NEED_DATA
                dbPosition.lastupdatedat = timezone.now()
                positionsToUpdate.append(dbPosition)
                closedCount += 1
        
        return closedCount

    @staticmethod
    def _processReopenedPositions(walletId: int, 
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
        
        closedPositionMap = PositionPersistenceHandler._createDbPositionMap(closedPositions)
        reopenedCount = 0
        
        for key in apiKeysNotInOpen:
            if key in closedPositionMap:
                closedPosition = closedPositionMap[key]
                apiPosition = apiPositionMap[key]
                
                # Update closed position to open status
                PositionPersistenceHandler._updatePositionFromApi(closedPosition, apiPosition)
                closedPosition.positionstatus = PositionStatus.OPEN
                closedPosition.tradestatus = TradeStatus.NEED_TO_PULL_TRADES
                closedPosition.lastupdatedat = timezone.now()
                positionsToUpdate.append(closedPosition)
                reopenedCount += 1
        
        return reopenedCount

    @staticmethod
    def _createApiPositionMap(openPositions: List[PolymarketPositionResponse]) -> Dict[str, PolymarketPositionResponse]:
        """Create lookup map: conditionId+outcome -> PolymarketPositionResponse"""
        apiMap = {}
        for position in openPositions:
            key = f"{position.conditionId}_{position.outcome}"
            apiMap[key] = position
        return apiMap

    @staticmethod
    def _createDbPositionMap(dbPositions: List[PositionModel]) -> Dict[str, PositionModel]:
        """Create lookup map: conditionId+outcome -> Position model"""
        dbMap = {}
        for position in dbPositions:
            key = f"{position.conditionid}_{position.outcome}"
            dbMap[key] = position
        return dbMap

    @staticmethod
    def _needsUpdate(dbPosition: PositionModel, apiPosition: PolymarketPositionResponse) -> bool:
        """
        Check if database position needs update based on API response.
        Compare key fields that might change.
        """
        # Compare total shares (size from API)
        if abs(float(dbPosition.totalshares) - float(apiPosition.size or 0)) > 0.000001:
            return True
            
        # Compare average entry price
        if abs(float(dbPosition.averageentryprice) - float(apiPosition.avgPrice or 0)) > 0.000001:
            return True
            
        # Compare current value
        if abs(float(dbPosition.amountremaining) - float(apiPosition.currentValue or 0)) > 0.01:
            return True
            
        # Compare amount spent (totalBought * avgPrice)
        expectedAmountSpent = float(apiPosition.totalBought or 0) * float(apiPosition.avgPrice or 0)
        if abs(float(dbPosition.amountspent) - expectedAmountSpent) > 0.01:
            return True
        
        return False

    @staticmethod  
    def _updatePositionFromApi(dbPosition: PositionModel, apiPosition: PolymarketPositionResponse) -> None:
        """
        Update database position fields from API response.
        Maps API fields to database model fields.
        """
        dbPosition.totalshares = Decimal(str(apiPosition.size or 0))
        dbPosition.currentshares = Decimal(str(apiPosition.size or 0))  # Same as totalshares for open
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
                'amountspent', 'amountremaining', 'tradestatus', 'lastupdatedat'
            ],
            batch_size=500
        )
