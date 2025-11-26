#!/usr/bin/env python
"""
Test Script for Wallet Acquisition Process

This script tests the complete wallet acquisition pipeline:
1. Fetching wallets from Polymarket API
2. Bulk persistence with optimized 2-query approach
3. Wallet type tracking (new vs old)
4. Category stats upserting

Usage:
    python test_wallet_acquisition.py
"""

import os
import sys
import django
from decimal import Decimal
from datetime import datetime

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

# Now import Django-dependent modules
from django.utils import timezone
from django.db import connection
from wallets.WalletsAPI import WalletsAPI
from wallets.models import Wallet, WalletCategoryStat
from wallets.enums import WalletType
from wallets.implementations.polymarket.Constants import TIME_PERIOD_MONTH, SMART_MONEY_CATEGORIES
from wallets.Constants import PLATFORM_POLYMARKET


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text):
    """Print a formatted header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(80)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}\n")


def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")


def print_info(text):
    """Print info message"""
    print(f"{Colors.CYAN}ℹ {text}{Colors.ENDC}")


def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.ENDC}")


def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.ENDC}")


def print_section(text):
    """Print section header"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}## {text}{Colors.ENDC}")


def print_db_queries():
    """Print database query count"""
    query_count = len(connection.queries)
    print(f"{Colors.YELLOW}📊 Database Queries: {query_count}{Colors.ENDC}")
    return query_count


def get_database_stats():
    """Get current database statistics"""
    wallet_count = Wallet.objects.count()
    new_wallet_count = Wallet.objects.filter(wallettype=WalletType.NEW).count()
    old_wallet_count = Wallet.objects.filter(wallettype=WalletType.OLD).count()
    stat_count = WalletCategoryStat.objects.count()
    
    return {
        'total_wallets': wallet_count,
        'new_wallets': new_wallet_count,
        'old_wallets': old_wallet_count,
        'total_stats': stat_count
    }


def print_database_stats(stats, title="Database Statistics"):
    """Print database statistics in a formatted way"""
    print_section(title)
    print(f"  Total Wallets:    {Colors.BOLD}{stats['total_wallets']:>6}{Colors.ENDC}")
    print(f"    - New Wallets:  {Colors.GREEN}{stats['new_wallets']:>6}{Colors.ENDC}")
    print(f"    - Old Wallets:  {Colors.CYAN}{stats['old_wallets']:>6}{Colors.ENDC}")
    print(f"  Category Stats:   {Colors.BOLD}{stats['total_stats']:>6}{Colors.ENDC}")


def test_single_category():
    """Test fetching wallets for a single category"""
    print_header("TEST 1: Single Category Acquisition (Politics)")
    
    # Get initial stats
    initial_stats = get_database_stats()
    print_database_stats(initial_stats, "Initial State")
    
    # Clear query log
    connection.queries.clear()
    
    # Fetch wallets
    print_section("Fetching Wallets")
    print_info("Category: politics")
    print_info(f"Time Period: {TIME_PERIOD_MONTH}")
    
    api = WalletsAPI()
    start_time = datetime.now()
    response = api.fetchPolymarketCategories(categories=["politics"], timePeriod=TIME_PERIOD_MONTH)
    end_time = datetime.now()
    
    execution_time = (end_time - start_time).total_seconds()
    
    # Print results
    print_section("Execution Results")
    if response.success:
        print_success(f"Fetch completed successfully")
        print_info(f"Execution Time: {execution_time:.2f} seconds")
        print_info(f"Wallets Created: {response.walletsCreated}")
        print_info(f"Wallets Updated: {response.walletsUpdated}")
        print_info(f"Stats Created: {response.statsCreated}")
        print_info(f"Total Processed: {response.totalProcessed}")
        
        if hasattr(response, 'processingTimeSeconds'):
            print_info(f"Processing Time: {response.processingTimeSeconds:.2f} seconds")
    else:
        print_error(f"Fetch failed: {response.errorMessage}")
        return False
    
    # Print query count
    query_count = print_db_queries()
    
    # Get final stats
    final_stats = get_database_stats()
    print_database_stats(final_stats, "Final State")
    
    # Calculate changes
    print_section("Changes")
    print(f"  Wallets Added:    {Colors.GREEN}+{final_stats['total_wallets'] - initial_stats['total_wallets']}{Colors.ENDC}")
    print(f"  New Wallets:      {Colors.GREEN}+{final_stats['new_wallets'] - initial_stats['new_wallets']}{Colors.ENDC}")
    print(f"  Stats Added:      {Colors.GREEN}+{final_stats['total_stats'] - initial_stats['total_stats']}{Colors.ENDC}")
    
    return True


def test_multiple_categories():
    """Test fetching wallets for multiple categories"""
    print_header("TEST 2: Multiple Categories Acquisition")
    
    # Get initial stats
    initial_stats = get_database_stats()
    print_database_stats(initial_stats, "Initial State")
    
    # Clear query log
    connection.queries.clear()
    
    # Fetch wallets
    categories = ["sports", "crypto"]
    print_section("Fetching Wallets")
    print_info(f"Categories: {', '.join(categories)}")
    print_info(f"Time Period: {TIME_PERIOD_MONTH}")
    
    api = WalletsAPI()
    start_time = datetime.now()
    response = api.fetchPolymarketCategories(categories=categories, timePeriod=TIME_PERIOD_MONTH)
    end_time = datetime.now()
    
    execution_time = (end_time - start_time).total_seconds()
    
    # Print results
    print_section("Execution Results")
    if response.success:
        print_success(f"Fetch completed successfully")
        print_info(f"Execution Time: {execution_time:.2f} seconds")
        print_info(f"Wallets Created: {response.walletsCreated}")
        print_info(f"Wallets Updated: {response.walletsUpdated}")
        print_info(f"Stats Created: {response.statsCreated}")
        print_info(f"Total Processed: {response.totalProcessed}")
    else:
        print_error(f"Fetch failed: {response.errorMessage}")
        return False
    
    # Print query count
    query_count = print_db_queries()
    
    # Get final stats
    final_stats = get_database_stats()
    print_database_stats(final_stats, "Final State")
    
    # Calculate changes
    print_section("Changes")
    print(f"  Wallets Added:    {Colors.GREEN}+{final_stats['total_wallets'] - initial_stats['total_wallets']}{Colors.ENDC}")
    print(f"  Stats Added:      {Colors.GREEN}+{final_stats['total_stats'] - initial_stats['total_stats']}{Colors.ENDC}")
    
    return True


def test_wallet_type_tracking():
    """Test that wallet types are tracked correctly"""
    print_header("TEST 3: Wallet Type Tracking")
    
    # Get some sample wallets
    new_wallets = list(Wallet.objects.filter(wallettype=WalletType.NEW)[:5])
    old_wallets = list(Wallet.objects.filter(wallettype=WalletType.OLD)[:5])
    
    print_section("New Wallets Sample")
    if new_wallets:
        for wallet in new_wallets:
            print(f"  {Colors.GREEN}• {wallet.username} ({wallet.proxywallet[:10]}...){Colors.ENDC}")
            print(f"    Type: {wallet.wallettype}, Active: {wallet.is_active_bool}")
    else:
        print_warning("No new wallets found. Run test again after database reset.")
    
    print_section("Old Wallets Sample")
    if old_wallets:
        for wallet in old_wallets:
            print(f"  {Colors.CYAN}• {wallet.username} ({wallet.proxywallet[:10]}...){Colors.ENDC}")
            print(f"    Type: {wallet.wallettype}, Active: {wallet.is_active_bool}")
    else:
        print_info("No old wallets found (all wallets are new)")
    
    return True


def test_re_fetch_existing():
    """Test re-fetching existing wallets to ensure wallettype is preserved"""
    print_header("TEST 4: Re-fetch Existing Wallets (Type Preservation)")
    
    # Get stats before
    stats_before = get_database_stats()
    print_database_stats(stats_before, "Before Re-fetch")
    
    # Get a wallet that should exist
    sample_wallet = Wallet.objects.first()
    if not sample_wallet:
        print_warning("No wallets in database. Run previous tests first.")
        return False
    
    original_type = sample_wallet.wallettype
    print_info(f"Sample wallet: {sample_wallet.username} (Type: {original_type})")
    
    # Clear query log
    connection.queries.clear()
    
    # Re-fetch the same category
    print_section("Re-fetching Politics Category")
    api = WalletsAPI()
    response = api.fetchPolymarketCategories(categories=["politics"], timePeriod=TIME_PERIOD_MONTH)
    
    if not response.success:
        print_error(f"Re-fetch failed: {response.errorMessage}")
        return False
    
    print_success("Re-fetch completed")
    print_info(f"Wallets Created: {response.walletsCreated} (should be 0 or low)")
    print_info(f"Wallets Updated: {response.walletsUpdated} (should include existing)")
    print_info(f"Stats Created: {response.statsCreated}")
    
    # Print query count
    query_count = print_db_queries()
    
    # Check if wallet type is preserved
    sample_wallet.refresh_from_db()
    print_section("Wallet Type Verification")
    
    if sample_wallet.wallettype == original_type:
        print_success(f"✓ Wallet type preserved: {original_type}")
    else:
        print_error(f"✗ Wallet type CHANGED: {original_type} → {sample_wallet.wallettype}")
        return False
    
    # Get stats after
    stats_after = get_database_stats()
    print_database_stats(stats_after, "After Re-fetch")
    
    # Verify new wallet count didn't change much (maybe a few new ones)
    if stats_after['new_wallets'] >= stats_before['new_wallets']:
        print_success("New wallet count is stable or slightly increased")
    else:
        print_error("New wallet count decreased (should not happen!)")
        return False
    
    return True


def test_query_performance():
    """Test and display query performance metrics"""
    print_header("TEST 5: Query Performance Analysis")
    
    print_section("Performance Metrics")
    
    # Test with different data sizes
    test_cases = [
        ("Single Category", ["politics"]),
        ("Two Categories", ["sports", "crypto"]),
    ]
    
    for test_name, categories in test_cases:
        connection.queries.clear()
        
        api = WalletsAPI()
        start_time = datetime.now()
        response = api.fetchPolymarketCategories(categories=categories, timePeriod=TIME_PERIOD_MONTH)
        end_time = datetime.now()
        
        if response.success:
            execution_time = (end_time - start_time).total_seconds()
            query_count = len(connection.queries)
            
            print(f"\n  {Colors.BOLD}{test_name}:{Colors.ENDC}")
            print(f"    Wallets Processed: {response.totalProcessed}")
            print(f"    Execution Time:    {execution_time:.2f}s")
            print(f"    DB Queries:        {query_count}")
            print(f"    Stats Upserted:    {response.statsCreated}")
            
            if response.totalProcessed > 0:
                avg_time = execution_time / response.totalProcessed
                print(f"    Avg Time/Wallet:   {avg_time*1000:.2f}ms")
    
    return True


def main():
    """Main test execution"""
    print_header("🧪 Wallet Acquisition Test Suite")
    print(f"{Colors.CYAN}Testing optimized 2-query bulk persistence approach{Colors.ENDC}")
    print(f"{Colors.CYAN}Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.ENDC}")
    
    tests = [
        ("Single Category Fetch", test_single_category),
        ("Multiple Categories Fetch", test_multiple_categories),
        ("Wallet Type Tracking", test_wallet_type_tracking),
        ("Re-fetch & Type Preservation", test_re_fetch_existing),
        ("Query Performance", test_query_performance),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print_error(f"Test failed with exception: {str(e)}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Print final summary
    print_header("📊 Test Summary")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = f"{Colors.GREEN}✓ PASS{Colors.ENDC}" if result else f"{Colors.RED}✗ FAIL{Colors.ENDC}"
        print(f"  {status}  {test_name}")
    
    print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed{Colors.ENDC}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 All tests passed!{Colors.ENDC}")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ Some tests failed{Colors.ENDC}")
        return 1


if __name__ == "__main__":
    sys.exit(main())





