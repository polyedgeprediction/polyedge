"""
Trade type enumeration for different transaction types in Polymarket.
"""
from enum import Enum


class TradeType(Enum):
    """
    Enumeration for different types of trades/transactions.
    Maps to Polymarket API transaction types with proper aggregation logic.
    """
    
    BUY = 1
    SELL = 2
    MERGE = 3
    SPLIT = 4
    REDEEM = 5

    @classmethod
    def choices(cls):
        """Django model choices format"""
        return [
            (cls.BUY.value, 'BUY'),
            (cls.SELL.value, 'SELL'),
            (cls.MERGE.value, 'MERGE'),
            (cls.SPLIT.value, 'SPLIT'),
            (cls.REDEEM.value, 'REDEEM'),
        ]

    @classmethod
    def get_label(cls, value):
        """Get string label for enum value"""
        label_map = {
            cls.BUY.value: 'BUY',
            cls.SELL.value: 'SELL',
            cls.MERGE.value: 'MERGE',
            cls.SPLIT.value: 'SPLIT',
            cls.REDEEM.value: 'REDEEM',
        }
        return label_map.get(value, 'UNKNOWN')

    @classmethod
    def from_api_type(cls, api_type: str, side: str = None):
        """
        Convert Polymarket API type to our TradeType enum.
        
        Args:
            api_type: API transaction type ('TRADE', 'MERGE', 'SPLIT', 'REDEEM')
            side: For TRADE type, specifies 'BUY' or 'SELL'
        
        Returns:
            TradeType enum value
        """
        if api_type == 'TRADE':
            if side == 'BUY':
                return cls.BUY
            elif side == 'SELL':
                return cls.SELL
            else:
                raise ValueError(f"Invalid side '{side}' for TRADE type")
        elif api_type == 'MERGE':
            return cls.MERGE
        elif api_type == 'SPLIT':
            return cls.SPLIT
        elif api_type == 'REDEEM':
            return cls.REDEEM
        else:
            raise ValueError(f"Unknown API type: {api_type}")

    @classmethod
    def get_investment_types(cls):
        """Get trade types that represent investment (money out)"""
        return [cls.BUY, cls.SPLIT]

    @classmethod
    def get_divestment_types(cls):
        """Get trade types that represent divestment (money in)"""
        return [cls.SELL, cls.MERGE, cls.REDEEM]

    def is_investment_type(self):
        """Check if this trade type represents investment"""
        return self in self.get_investment_types()

    def is_divestment_type(self):
        """Check if this trade type represents divestment"""
        return self in self.get_divestment_types()