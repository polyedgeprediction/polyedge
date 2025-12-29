"""
Constants for Smart Wallet Discovery.
Contains blacklist of wallet addresses to exclude from discovery process.
"""
from typing import Set

# Blacklisted wallet addresses (proxy wallets)
# Wallets in this list will be filtered out during candidate fetching
# and will not be evaluated or persisted to the database
BLACKLISTED_WALLETS: Set[str] = {
    # Add wallet addresses here to blacklist them
    # Example: "0x1234567890abcdef1234567890abcdef12345678"
}


def isWalletBlacklisted(walletAddress: str) -> bool:
    return walletAddress in BLACKLISTED_WALLETS
