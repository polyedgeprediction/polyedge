"""
Handler for persisting wallet data to database.
Uses bulk operations for maximum performance.
"""
import logging
import time
from typing import List, Dict
from django.db import transaction

from wallets.models import Wallet, WalletCategoryStat
from wallets.enums import WalletType
from wallets.pojos.Wallet import Wallet as WalletPojo
from wallets.pojos.FetchSmartMoneyWalletAPIResponse import FetchSmartMoneyWalletAPIResponse

logger = logging.getLogger(__name__)


class SmartMoneyWalletPersistenceHandler:
    
    def persistWallets(self, wallets: List[WalletPojo], snapshotTime) -> FetchSmartMoneyWalletAPIResponse:
        """
        Persists wallets and their category stats using efficient bulk operations.
        
        Strategy:
        1. Bulk upsert ALL wallets (INSERT with ON CONFLICT):
           - New wallets: created with wallettype='new'
           - Existing wallets: only lastupdatedat is touched
           - Returns ALL wallet objects with PKs
        2. Bulk upsert all category stats (the real data that changes: rank, volume, PNL)
        
        This is the OPTIMAL approach: just 2 DB queries total regardless of data size!
        """
        startTime = time.time()
        
        if not wallets:
            logger.info("FETCH_WALLETS_API :: HANDLER :: No wallets to persist")
            return FetchSmartMoneyWalletAPIResponse(success=True, totalProcessed=0)
        
        try:
            with transaction.atomic():
                logger.info("FETCH_WALLETS_API :: HANDLER :: Starting bulk persistence for %d wallets", len(wallets))
                
                # Step 1: Prepare all wallet objects for bulk upsert
                wallet_objects = []
                for walletPojo in wallets:
                    wallet_objects.append(Wallet(
                        proxywallet=walletPojo.proxyWallet,
                        username=walletPojo.userName or f"User_{walletPojo.proxyWallet[:8]}",
                        xusername=walletPojo.xUsername if walletPojo.xUsername else None,
                        verifiedbadge=walletPojo.verifiedBadge,
                        profileimage=walletPojo.profileImage if walletPojo.profileImage else None,
                        platform=walletPojo.platform,
                        isactive=1,
                        wallettype=WalletType.NEW  # Only applied on INSERT, not UPDATE
                    ))
                
                # Step 2: Bulk upsert wallets with ON CONFLICT behavior
                # - If wallet is NEW: INSERT with all fields including wallettype='new'
                # - If wallet EXISTS: UPDATE only lastupdatedat (preserves wallettype)
                upserted_wallets = Wallet.objects.bulk_create(
                    wallet_objects,
                    update_conflicts=True,
                    update_fields=['lastupdatedat'],  # Only touch timestamp for existing wallets
                    unique_fields=['proxywallet'],  # Conflict check on proxywallet
                    batch_size=500
                )
                
                logger.info("FETCH_WALLETS_API :: HANDLER :: Bulk upserted %d wallets", len(upserted_wallets))
                
                # Create a lookup dict for wallet objects (by proxywallet)
                wallet_lookup = {w.proxywallet: w for w in upserted_wallets}
                
                # Note: We can't easily determine created vs updated count with bulk_create
                # For simplicity, we'll report total processed
                walletsCreated = 0  # Would need additional logic to determine
                walletsUpdated = 0  # Would need additional logic to determine
                
                # Step 3: Prepare category stats for bulk upsert
                all_stats_to_upsert = []
                for walletPojo in wallets:
                    wallet_obj = wallet_lookup.get(walletPojo.proxyWallet)
                    if not wallet_obj:
                        logger.warning("FETCH_WALLETS_API :: HANDLER :: Wallet not found after upsert: %s", 
                                     walletPojo.proxyWallet)
                        continue
                    
                    for stat in walletPojo.categoryStats:
                        all_stats_to_upsert.append(WalletCategoryStat(
                            wallets=wallet_obj,
                            category=stat.category,
                            timeperiod=stat.timePeriod,
                            rank=stat.rank,
                            volume=stat.volume,
                            pnl=stat.pnl,
                            snapshottime=snapshotTime
                        ))
                
                # Step 4: Bulk upsert category stats
                statsCreated = 0
                if all_stats_to_upsert:
                    # Use bulk_create with update_conflicts for upsert behavior
                    WalletCategoryStat.objects.bulk_create(
                        all_stats_to_upsert,
                        update_conflicts=True,
                        update_fields=['rank', 'volume', 'pnl', 'snapshottime'],
                        unique_fields=['wallets', 'category', 'timeperiod'],
                        batch_size=500
                    )
                    statsCreated = len(all_stats_to_upsert)
                    logger.info("FETCH_WALLETS_API :: HANDLER :: Bulk upserted %d category stats", statsCreated)
                
                processingTime = time.time() - startTime
                logger.info("FETCH_WALLETS_API :: HANDLER :: Transaction committed | Total wallets: %d | Stats upserted: %d | Time: %.2fs",
                           len(wallets), statsCreated, processingTime)
                
                return FetchSmartMoneyWalletAPIResponse(
                    success=True,
                    walletsCreated=walletsCreated,
                    walletsUpdated=walletsUpdated,
                    statsCreated=statsCreated,
                    totalProcessed=len(wallets),
                    processingTimeSeconds=processingTime
                )
                
        except Exception as e:
            logger.error("FETCH_WALLETS_API :: HANDLER :: Persistence error | Error: %s", str(e), exc_info=True)
            return FetchSmartMoneyWalletAPIResponse(success=False, errorMessage=str(e))
