"""
Parser for Polymarket smart money API responses.
"""
import logging
from typing import List, Dict, Any
from decimal import Decimal

from wallets.pojos.Wallet import Wallet, WalletCategoryStat

logger = logging.getLogger(__name__)


class PolymarketSmartMoneyParser:
    
    def parseAndUpdateWallets(self, data: List[Dict[str, Any]], category: str, timePeriod: str, platform: str, walletMap: Dict[str, Wallet], minPnlThreshold: float = 10000) -> bool:
        if not isinstance(data, list):
            return False
        
        foundLowPnl = False
        
        for item in data:
            try:
                proxyWallet = str(item.get("proxyWallet", ""))
                pnl = float(item.get("pnl", 0))
                
                if not proxyWallet or not proxyWallet.startswith("0x"):
                    continue
                
                if pnl < minPnlThreshold:
                    foundLowPnl = True
                    break
                
                if proxyWallet not in walletMap:
                    wallet = Wallet(
                        proxyWallet=proxyWallet,
                        userName=str(item.get("userName", "")),
                        xUsername=str(item.get("xUsername", "")),
                        verifiedBadge=bool(item.get("verifiedBadge", False)),
                        profileImage=str(item.get("profileImage", "")),
                        platform=platform
                    )
                    walletMap[proxyWallet] = wallet
                else:
                    wallet = walletMap[proxyWallet]
                
                categoryStat = WalletCategoryStat(
                    category=category,
                    timePeriod=timePeriod,
                    rank=int(item.get("rank", 0)),
                    volume=Decimal(str(item.get("vol", 0.0))),
                    pnl=Decimal(str(pnl))
                )
                
                wallet.addCategoryStat(categoryStat)
                
            except Exception as e:
                logger.info("FETCH_WALLETS_API :: PARSER :: Skipped entry %s: %s", item.get('proxyWallet', 'unknown'), str(e))
                continue
        
        return foundLowPnl
