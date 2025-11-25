import sys
from django.apps import AppConfig


class PositionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'positions'

    def ready(self):
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            import os
            if os.environ.get('RUN_MAIN') != 'false':
                from config.scheduler import getScheduler
                from positions.schedulers.Scheduler import configurePositionJobs
                
                configurePositionJobs(getScheduler())
