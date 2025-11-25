import sys
from django.apps import AppConfig


class WalletsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'wallets'

    def ready(self):
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            import os
            if os.environ.get('RUN_MAIN') != 'false':
                from config.scheduler import getScheduler
                from wallets.Scheduler import configureWalletJobs
                
                configureWalletJobs(getScheduler())
