#!/usr/bin/env python
"""
Quick Test for Wallet Acquisition

Simple script to quickly test wallet fetching for a single category.

Usage:
    python quick_test_wallets.py [category] [time_period]
    
Examples:
    python quick_test_wallets.py politics month
    python quick_test_wallets.py sports week
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.utils import timezone
from wallets.WalletsAPI import WalletsAPI
from wallets.models import Wallet, WalletCategoryStat
from wallets.enums import WalletType
from wallets.implementations.polymarket.Constants import (
    TIME_PERIOD_MONTH, TIME_PERIOD_WEEK, TIME_PERIOD_DAY, TIME_PERIOD_ALL
)


def main():
    # Get arguments
    category = sys.argv[1] if len(sys.argv) > 1 else "politics"
    time_period = sys.argv[2] if len(sys.argv) > 2 else TIME_PERIOD_MONTH
    
    print("="*80)
    print("QUICK WALLET ACQUISITION TEST".center(80))
    print("="*80)
    print(f"\nCategory: {category}")
    print(f"Time Period: {time_period}")
    
    # Get initial counts
    initial_wallets = Wallet.objects.count()
    initial_new = Wallet.objects.filter(wallettype=WalletType.NEW).count()
    initial_stats = WalletCategoryStat.objects.count()
    
    print(f"\nInitial State:")
    print(f"  Total Wallets: {initial_wallets}")
    print(f"  New Wallets:   {initial_new}")
    print(f"  Total Stats:   {initial_stats}")
    
    # Fetch wallets
    print(f"\nFetching wallets...")
    api = WalletsAPI()
    response = api.fetchPolymarketCategories(categories=[category], timePeriod=time_period)
    
    # Print results
    print(f"\n{'='*80}")
    if response.success:
        print("✓ SUCCESS")
        print(f"{'='*80}")
        print(f"\nResults:")
        print(f"  Wallets Created:  {response.walletsCreated}")
        print(f"  Wallets Updated:  {response.walletsUpdated}")
        print(f"  Stats Created:    {response.statsCreated}")
        print(f"  Total Processed:  {response.totalProcessed}")
        
        if hasattr(response, 'processingTimeSeconds'):
            print(f"  Processing Time:  {response.processingTimeSeconds:.2f}s")
        
        # Get final counts
        final_wallets = Wallet.objects.count()
        final_new = Wallet.objects.filter(wallettype=WalletType.NEW).count()
        final_stats = WalletCategoryStat.objects.count()
        
        print(f"\nFinal State:")
        print(f"  Total Wallets: {final_wallets} (+{final_wallets - initial_wallets})")
        print(f"  New Wallets:   {final_new} (+{final_new - initial_new})")
        print(f"  Total Stats:   {final_stats} (+{final_stats - initial_stats})")
        
        # Show some sample wallets
        print(f"\nSample New Wallets:")
        new_wallets = Wallet.objects.filter(wallettype=WalletType.NEW).order_by('-firstseenat')[:5]
        for wallet in new_wallets:
            stats_count = wallet.category_stats.count()
            print(f"  • {wallet.username[:30]:30} | {wallet.proxywallet[:12]}... | {stats_count} stats")
        
    else:
        print("✗ FAILED")
        print(f"{'='*80}")
        print(f"Error: {response.errorMessage}")
        return 1
    
    print(f"\n{'='*80}")
    print("Test completed successfully!")
    print("="*80)
    return 0


if __name__ == "__main__":
    sys.exit(main())





