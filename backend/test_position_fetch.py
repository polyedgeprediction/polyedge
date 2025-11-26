"""
Test script for position fetching functionality.
Demonstrates the clean, modular architecture.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from positions.schedulers.FetchPositionsScheduler import FetchPositionsScheduler
from positions.actions.PositionAction import PositionAction
from wallets.models import Wallet
from wallets.enums import WalletType


def testFetchPositionsScheduler():
    """
    Test the scheduler that processes all NEW wallets.
    """
    print("=" * 80)
    print("TEST: Fetch Positions Scheduler")
    print("=" * 80)
    
    # Check for NEW wallets
    newWallets = Wallet.objects.filter(wallettype=WalletType.NEW, isactive=1)
    print(f"\nFound {newWallets.count()} NEW wallets")
    
    if newWallets.count() == 0:
        print("\nNo NEW wallets found. Create a wallet first:")
        print("Example:")
        print("  wallet = Wallet.objects.create(")
        print("      proxywallet='0xf705fa045201391d9632b7f3cde06a5e24453ca7',")
        print("      username='TestUser',")
        print("      wallettype=WalletType.NEW,")
        print("      isactive=1")
        print("  )")
        return
    
    # Show wallets to be processed
    print("\nWallets to process:")
    for idx, wallet in enumerate(newWallets[:5], 1):
        print(f"  {idx}. {wallet.username} ({wallet.proxywallet[:10]}...)")
    if newWallets.count() > 5:
        print(f"  ... and {newWallets.count() - 5} more")
    
    # Execute scheduler
    print("\n" + "-" * 80)
    print("Starting scheduler execution...")
    print("-" * 80 + "\n")
    
    result = FetchPositionsScheduler.execute()
    
    # Display results
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"Success: {result['success']}")
    print(f"Wallets Processed: {result['walletsProcessed']}")
    print(f"Wallets Succeeded: {result['walletsSucceeded']}")
    print(f"Wallets Failed: {result['walletsFailed']}")
    print(f"Total Positions Created: {result['totalPositionsCreated']}")
    print(f"Total Positions Updated: {result['totalPositionsUpdated']}")
    print(f"Total Events Created: {result['totalEventsCreated']}")
    print(f"Total Markets Created: {result['totalMarketsCreated']}")
    print("=" * 80)


def testFetchPositionsForSingleWallet(walletAddress: str = None):
    """
    Test fetching positions for a single wallet.
    """
    print("=" * 80)
    print("TEST: Fetch Positions for Single Wallet")
    print("=" * 80)
    
    if not walletAddress:
        # Use a known wallet with positions
        walletAddress = "0xf705fa045201391d9632b7f3cde06a5e24453ca7"
    
    # Get or create wallet
    wallet, created = Wallet.objects.get_or_create(
        proxywallet=walletAddress,
        defaults={
            'username': f'TestUser_{walletAddress[:8]}',
            'wallettype': WalletType.NEW,
            'isactive': 1
        }
    )
    
    print(f"\nProcessing wallet: {wallet.proxywallet}")
    print(f"Username: {wallet.username}")
    print(f"Wallet type: {wallet.wallettype}")
    
    # Execute action
    print("\n" + "-" * 80)
    print("Starting position fetch...")
    print("-" * 80 + "\n")
    
    positionAction = PositionAction()
    response = positionAction.fetchAndPersistPositionsForWallet(wallet)
    
    # Display results
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"Success: {response.success}")
    print(f"Total Processed: {response.totalProcessed}")
    print(f"Positions Created: {response.positionsCreated}")
    print(f"Positions Updated: {response.positionsUpdated}")
    print(f"Events Created: {response.eventsCreated}")
    print(f"Markets Created: {response.marketsCreated}")
    print(f"Processing Time: {response.processingTimeSeconds:.2f}s")
    if not response.success:
        print(f"Error: {response.errorMessage}")
    print("=" * 80)


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "POSITION FETCH TEST SUITE" + " " * 33 + "║")
    print("╚" + "=" * 78 + "╝")
    print("\n")
    
    # Run tests
    try:
        # Test 1: Fetch for single wallet
        testFetchPositionsForSingleWallet()
        
        print("\n\n")
        
        # Test 2: Run full scheduler (uncomment to execute)
        # testFetchPositionsScheduler()
        
        print("\n✓ Tests completed successfully!\n")
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {str(e)}\n")
        import traceback
        traceback.print_exc()
