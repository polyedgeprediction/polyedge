from django.apps import AppConfig
import sys


class WalletsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'wallets'

    def ready(self):
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            import os
            if os.environ.get('RUN_MAIN') != 'false':
                from wallets.Scheduler import WalletScheduler
                scheduler = WalletScheduler()
                scheduler.start()
