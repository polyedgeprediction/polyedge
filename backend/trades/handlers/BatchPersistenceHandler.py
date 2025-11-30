"""
Handler for creating batch records from position data.
"""
from django.utils import timezone
from django.db import connection

from positions.enums.PositionStatus import PositionStatus
from wallets.enums import WalletType


class BatchPersistenceHandler:
    
    @staticmethod
    def createMissingBatchesForOpenPositions() -> int:
        """
        Create missing batch records using single optimized INSERT query.
        Finds wallet-market pairs that exist in open positions but not in batches.
        
        Returns:
            Number of batch records created
        """
        currentTime = timezone.now()
        
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO batches (walletsid, marketsid, isactive, createdat, lastupdatedat)
                SELECT DISTINCT p.walletsid, p.marketsid, 1, %s, %s
                FROM positions p
                INNER JOIN wallets w ON p.walletsid = w.walletsid
                LEFT JOIN batches b ON p.walletsid = b.walletsid 
                                   AND p.marketsid = b.marketsid 
                                   AND b.isactive = 1
                WHERE p.positionstatus = %s 
                  AND w.wallettype = %s 
                  AND w.isactive = 1
                  AND b.batchid IS NULL
            """, [currentTime, currentTime, PositionStatus.OPEN.value, WalletType.OLD.value])
            
            return cursor.rowcount