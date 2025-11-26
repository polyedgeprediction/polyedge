"""
Config app - SINGLE scheduler initialization point.
Prevents multiple scheduler instances.
"""
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class ConfigConfig(AppConfig):
    """
    Config app configuration.
    Initializes scheduler EXACTLY ONCE.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'config'

    def ready(self):
        """
        Initialize scheduler and register all jobs.
        Called ONCE when Django starts.
        """
        # Avoid initialization during migrations/commands
        if self._shouldSkipInitialization():
            return
            
        # CRITICAL: Only run in main process, not auto-reloader
        import os
        if os.environ.get('RUN_MAIN') != 'true':
            logger.info("CONFIG_APP :: Skipping scheduler initialization (not main process)")
            return
            
        # Use post_migrate signal to ensure database is ready
        from django.db.models.signals import post_migrate
        post_migrate.connect(self._initializeScheduler, sender=self)
        logger.info("CONFIG_APP :: Scheduler initialization deferred to post_migrate")

    def _initializeScheduler(self, sender, **kwargs):
        """Initialize scheduler after database migrations are complete"""
        try:
            from config.schedulerConfig import registerAllJobs
            registerAllJobs()
            logger.info("CONFIG_APP :: Scheduler initialization completed")
            
        except Exception as e:
            logger.error(
                "CONFIG_APP :: Scheduler initialization failed | Error: %s",
                str(e),
                exc_info=True
            )

    def _shouldSkipInitialization(self) -> bool:
        """
        Skip scheduler initialization during:
        - Database migrations
        - Management commands (except runserver)
        - Testing
        """
        import sys
        
        # Skip during any migration-related commands
        migration_commands = ['migrate', 'makemigrations', 'showmigrations', 'sqlmigrate']
        if any(cmd in sys.argv for cmd in migration_commands):
            logger.info("CONFIG_APP :: Skipping scheduler initialization (migration command)")
            return True
            
        # Skip during testing
        if 'test' in sys.argv:
            logger.info("CONFIG_APP :: Skipping scheduler initialization (testing)")
            return True
            
        # Skip during management commands (except runserver)
        if 'manage.py' in sys.argv[0] and len(sys.argv) > 1:
            command = sys.argv[1]
            allowed_commands = ['runserver']
            if command not in allowed_commands:
                logger.info(f"CONFIG_APP :: Skipping scheduler initialization (command: {command})")
                return True
        
        return False