"""
Scheduler for updating recently closed positions that need closed position data.
Processes positions with status POSITION_CLOSED_NEED_DATA.
"""
import logging
from typing import List, Dict
from positions.enums.TradeStatus import TradeStatus
from positions.enums.PositionStatus import PositionStatus
from positions.implementations.polymarket.ClosedPositionAPI import ClosedPositionAPI
from positions.pojos.PolymarketPositionResponse import PolymarketPositionResponse
from positions.pojos.Position import Position as PositionPojo
from positions.handlers.PositionPersistenceHandler import PositionPersistenceHandler


logger = logging.getLogger(__name__)


class RecentlyClosedPositionsScheduler:
    def __init__(self):
        self.closedPositionAPI = ClosedPositionAPI()

    @staticmethod
    def execute():
        
        logger.info("RECENTLY_CLOSED_POSITIONS_SCHEDULER :: Started updating closed positions")
        RecentlyClosedPositionsScheduler.updateRecentlyClosedPositions()
        logger.info("RECENTLY_CLOSED_POSITIONS_SCHEDULER :: Completed updating closed positions")


    @staticmethod
    def updateRecentlyClosedPositions() -> None:
        """
        Update recently closed positions by fetching closed position data from API.
        
        Process:
        1. Get map of positions (key: proxywallet_conditionid_outcome, value: (positionId, PositionPojo))
        2. Group positions by (proxywallet, conditionId) to minimize API calls
        3. For each unique (proxywallet, conditionId) pair, fetch closed positions from API
        4. Match API responses to positions by outcome
        5. Update Position POJOs with API data
        6. Persist all updates in a single bulk operation
        """
        try:
            logger.info("RECENTLY_CLOSED_POSITIONS_SCHEDULER :: Started updating closed positions")
            
            # Step 1: Get positions map
            positionMap = PositionPersistenceHandler.getRecentlyClosedPosition()
            
            if not positionMap:
                logger.info("RECENTLY_CLOSED_POSITIONS_SCHEDULER :: No positions to update")
                return
            
            scheduler = RecentlyClosedPositionsScheduler()
            
            # Step 2: Group positions by (proxywallet, conditionId) for efficient API calls
            positionsByWalletAndMarket = scheduler.groupPositionsByWalletAndMarket(positionMap)
            
            # Step 3: Process each (proxywallet, conditionId) group
            allPositionUpdates = []
            for (proxyWallet, conditionId), positionEntries in positionsByWalletAndMarket.items():
                try:
                    updates = scheduler.processWalletMarketGroup(proxyWallet, conditionId, positionEntries)
                    allPositionUpdates.extend(updates)
                    
                    logger.info("RECENTLY_CLOSED_POSITIONS_SCHEDULER :: Processed | Wallet: %s | Market: %s | Updates: %d",proxyWallet[:10],conditionId[:10],len(updates))
                    
                except Exception as e:
                    logger.info("RECENTLY_CLOSED_POSITIONS_SCHEDULER :: Failed | Wallet: %s | Market: %s | Error: %s",proxyWallet[:10],conditionId[:10],str(e))
            
            # Step 4: Single bulk update at the end
            if allPositionUpdates:
                updatedCount = PositionPersistenceHandler.bulkUpdateClosedPositions(allPositionUpdates)
                logger.info("RECENTLY_CLOSED_POSITIONS_SCHEDULER :: Completed | Updated: %d positions",updatedCount)
            else:
                logger.info("RECENTLY_CLOSED_POSITIONS_SCHEDULER :: No updates to persist")
            
        except Exception as e:
            logger.error("RECENTLY_CLOSED_POSITIONS_SCHEDULER :: Failed: %s", str(e), exc_info=True)


    def groupPositionsByWalletAndMarket(self, positionMap: Dict[str, tuple]) -> Dict[tuple, List[tuple]]:
        
        grouped = {}
        
        for mapKey, (positionId, positionPojo) in positionMap.items():
            # Parse key: proxywallet_conditionid_outcome
            parts = mapKey.rsplit('_', 2)  # Split from right to handle outcomes with underscores
            if len(parts) != 3:
                logger.warning(
                    "RECENTLY_CLOSED_POSITIONS_SCHEDULER :: Invalid map key format: %s",
                    mapKey
                )
                continue
            
            proxyWallet = parts[0]
            conditionId = parts[1]
            outcome = parts[2]
            
            groupKey = (proxyWallet, conditionId)
            
            if groupKey not in grouped:
                grouped[groupKey] = []
            
            grouped[groupKey].append((positionId, outcome, positionPojo))
        
        return grouped

    def processWalletMarketGroup(self,proxyWallet: str,conditionId: str,positionEntries: List[tuple] = List[tuple]) -> List[Dict]:
        
        # Step 1: Fetch closed positions from API for this wallet and market
        apiPositions = self.closedPositionAPI.fetchClosedPositionsForMarket(proxyWallet,conditionId)
        
        if not apiPositions:
            logger.info("RECENTLY_CLOSED_POSITIONS_SCHEDULER :: No API data found | Wallet: %s | Market: %s",proxyWallet[:10],conditionId[:10])   
            return []
        
        # Step 2: Create O(1) lookup map: outcome -> PolymarketPositionResponse
        # Handle duplicate outcomes by keeping the first occurrence
        apiPositionLookup = {}
        for apiPos in apiPositions:
            if apiPos.outcome in apiPositionLookup:
                logger.info(
                    "RECENTLY_CLOSED_POSITIONS_SCHEDULER :: Duplicate outcome in API response | Wallet: %s | Market: %s | Outcome: %s",proxyWallet[:10],conditionId[:10],apiPos.outcome)
            else:
                apiPositionLookup[apiPos.outcome] = apiPos
        
        # Step 3: Match positions to API responses and build updates
        positionUpdates = []
        for positionId, outcome, positionPojo in positionEntries:
            if outcome not in apiPositionLookup:
                logger.info( "RECENTLY_CLOSED_POSITIONS_SCHEDULER :: No API match found | "
                    "PositionId: %d | Outcome: %s | Wallet: %s | Market: %s",positionId,outcome,proxyWallet[:10],conditionId[:10])
                continue
            
            apiPosition = apiPositionLookup[outcome]
            
            # Step 4: Update Position POJO with API data
            updatedPositionPojo = self.updatePositionFromAPI(positionPojo, apiPosition)
            
            # Step 5: Add positionId and updated POJO directly
            positionUpdates.append((positionId, updatedPositionPojo))
        
        return positionUpdates

    def updatePositionFromAPI(self,positionPojo: PositionPojo,apiPosition: PolymarketPositionResponse) -> PositionPojo:

        from decimal import Decimal
        
        # Calculate amountSpent from API data
        amountSpent = apiPosition.totalBought * apiPosition.avgPrice
        
        # Create updated Position POJO
        return PositionPojo(
            outcome=positionPojo.outcome,
            oppositeOutcome=positionPojo.oppositeOutcome,
            title=positionPojo.title,
            totalShares=apiPosition.totalBought,
            currentShares=Decimal('0'),  # Closed positions have 0 current shares
            averageEntryPrice=apiPosition.avgPrice,
            amountSpent=amountSpent,
            amountRemaining=Decimal('0'),  # Closed positions have 0 remaining
            apiRealizedPnl=apiPosition.realizedPnl,
            endDate=positionPojo.endDate,  # Keep existing endDate
            negativeRisk=positionPojo.negativeRisk,
            tradeStatus=TradeStatus.TRADES_SYNCED,
            positionStatus=PositionStatus.CLOSED
        )


