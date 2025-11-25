"""
Handler for persisting positions to database.
"""
from typing import Dict
from decimal import Decimal

from positions.models import Position
from positions.enums.PositionStatus import PositionStatus
from positions.enums.TradeStatus import TradeStatus
from wallets.models import Wallet
from markets.models import Market


class PositionPersistenceHandler:
    """
    Handles position persistence operations.
    """

    @staticmethod
    def persistPositions(wallet: Wallet, eventPojos: Dict[str, Dict], marketLookup: Dict[str, Market]) -> None:
        if not eventPojos or not marketLookup:
            return
        
        positionObjects = []
        for eventData in eventPojos.values():
            for conditionId, marketData in eventData['markets'].items():
                if conditionId in marketLookup:
                    for positionData in marketData['positions']:
                        positionObjects.append(Position(
                            walletsid=wallet,
                            marketsid=marketLookup[conditionId],
                            conditionid=conditionId,
                            outcome=positionData['outcome'],
                            oppositeoutcome=positionData['oppositeOutcome'],
                            title=positionData['title'],
                            positionstatus=PositionStatus.OPEN.value if positionData['isOpen'] else PositionStatus.CLOSED.value,
                            tradestatus=TradeStatus.NEED_TO_PULL_TRADES.value if positionData['isOpen'] else TradeStatus.PENDING.value,
                            totalshares=positionData['totalShares'],
                            currentshares=positionData['currentShares'],
                            averageentryprice=positionData['averageEntryPrice'],
                            amountspent=positionData['amountSpent'],
                            amountremaining=positionData['amountRemaining'],
                            calculatedamountinvested=Decimal('0'),
                            calculatedcurrentvalue=Decimal('0'),
                            calculatedamountout=Decimal('0'),
                            realizedpnl=Decimal('0'),
                            unrealizedpnl=Decimal('0'),
                            apirealizedpnl=positionData['apiRealizedPnl'],
                            enddate=positionData['endDate'],
                            negativerisk=positionData['negativeRisk']
                        ))
        
        if positionObjects:
            Position.objects.bulk_create(
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
