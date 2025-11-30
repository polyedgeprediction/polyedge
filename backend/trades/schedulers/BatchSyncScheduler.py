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
    def execute() -> Dict[str, any]:
        """
        Sync missing batch records using single optimized INSERT query.
        
        Returns:
            Execution statistics
        """
        logger.info("BATCH_SYNC_SCHEDULER :: Started")
        
        with transaction.atomic():
            batchesCreated = BatchPersistenceHandler.createMissingBatchesForOpenPositions()
            
            logger.info(
                "BATCH_SYNC_SCHEDULER :: Completed | Created: %d batches", 
                batchesCreated
            )
            
            return {'success': True, 'batchesCreated': batchesCreated}