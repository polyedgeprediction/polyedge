from django.core.management.base import BaseCommand
from wallets.WalletsAPI import WalletsAPI


class Command(BaseCommand):
    help = 'Fetch smart money wallets from Polymarket'

    def handle(self, *args, **options):
        self.stdout.write('Starting to fetch smart money wallets...')
        
        api = WalletsAPI()
        result = api.fetchAllPolymarketCategories()
        
        if result.success:
            self.stdout.write(self.style.SUCCESS('✓ Successfully fetched and persisted wallets'))
            self.stdout.write(f'  Wallets created: {result.walletsCreated}')
            self.stdout.write(f'  Wallets updated: {result.walletsUpdated}')
            self.stdout.write(f'  Category stats created: {result.statsCreated}')
            self.stdout.write(f'  Total processed: {result.totalProcessed}')
            self.stdout.write(f'  Time: {result.processingTimeSeconds:.2f}s')
        else:
            self.stdout.write(self.style.ERROR(f'✗ Error: {result.errorMessage}'))
