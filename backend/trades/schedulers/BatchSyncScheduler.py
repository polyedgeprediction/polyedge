"""
Scheduler that ensures all open positions have corresponding batch records.
"""
import logging
from typing import Dict
from django.db import transaction

from trades.handlers.BatchPersistenceHandler import BatchPersistenceHandler

logger = logging.getLogger(__name__)


class BatchSyncScheduler:
    
    @staticmethod
    def addMissingInitialBatchRecords() -> Dict[str, any]:
        logger.info("POSITION_UPDATES_SCHEDULER :: Started adding missing initial batch records")
        
        with transaction.atomic():
            batchesCreated = BatchPersistenceHandler.createMissingBatchesForOpenPositions()
            
            logger.info("POSITION_UPDATES_SCHEDULER :: Completed | Created: %d batches", batchesCreated)
            
            return {'success': True, 'batchesCreated': batchesCreated}