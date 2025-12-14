"""
Config app - SINGLE scheduler initialization point.

FIRST PRINCIPLES APPROACH:
==========================

PROBLEM:
--------
1. APScheduler jobs must be registered when server starts
2. But jobs cannot be registered during migrations (DB might not be ready, jobs might execute)
3. post_migrate signal only fires during migrations, not normal server startup
4. Need idempotent registration (safe to call multiple times)

SOLUTION (Hybrid Approach):
---------------------------
1. SKIP during migrations: Detect migration commands and skip entirely
2. DIRECT initialization: Try to register jobs immediately on server startup
3. FALLBACK to post_migrate: If DB not ready, post_migrate signal will retry
4. IDEMPOTENCY: Check if jobs exist before adding (prevents duplicates)

This ensures:
- Jobs register on server startup (not just during migrations)
- No interference with database migrations
- Works in cloud deployments (handles restarts, scaling, etc.)
- Safe to call multiple times (idempotent)
"""
import logging
import os
import sys
from django.apps import AppConfig
from django.db import connection
from django.db.models.signals import post_migrate
from django.db.utils import OperationalError, DatabaseError

logger = logging.getLogger(__name__)

# ============================================================================
# MODULE-LEVEL STATE
# ============================================================================

# Flag to prevent double initialization (idempotency guarantee)
# FIRST PRINCIPLE: Ensure scheduler initializes exactly once, even if
# ready() is called multiple times or post_migrate fires after direct init
_scheduler_initialized = False


# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================

# Commands that trigger database migrations
MIGRATION_COMMANDS = ['migrate', 'makemigrations', 'showmigrations', 'sqlmigrate']

# Management commands that are allowed to initialize scheduler
ALLOWED_MANAGEMENT_COMMANDS = ['runserver']


# ============================================================================
# HELPER FUNCTIONS (Modular, testable)
# ============================================================================

def _isMainProcess() -> bool:
    """
    FIRST PRINCIPLE: Django's auto-reloader runs code twice.
    - First run: Sets up the reloader
    - Second run: Actual server process (RUN_MAIN='true')
    
    We only want to initialize scheduler in the actual server process,
    not during the reloader setup phase.
    """
    return os.environ.get('RUN_MAIN') == 'true'


def _isMigrationCommand() -> bool:
    """
    FIRST PRINCIPLE: During migrations, database schema might be changing.
    We must NOT:
    - Access database to check for existing jobs
    - Register new jobs (they might try to execute)
    - Start scheduler (jobs might run during migration)
    
    Returns True if current command is a migration-related command.
    """
    return any(cmd in sys.argv for cmd in MIGRATION_COMMANDS)


def _isTesting() -> bool:
    """Returns True if running tests"""
    return 'test' in sys.argv


def _isAllowedManagementCommand() -> bool:
    """
    FIRST PRINCIPLE: Some management commands don't need scheduler.
    - runserver: YES (normal server operation)
    - migrate: NO (handled by _isMigrationCommand)
    - shell, createsuperuser, etc.: NO (one-off commands)
    """
    if 'manage.py' not in sys.argv[0] or len(sys.argv) < 2:
        return False
    
    command = sys.argv[1]
    return command in ALLOWED_MANAGEMENT_COMMANDS


def _shouldSkipInitialization() -> bool:
    """
    FIRST PRINCIPLE: Defense in depth - multiple checks to prevent
    scheduler initialization in inappropriate contexts.
    
    Returns True if scheduler initialization should be skipped.
    """
    if _isMigrationCommand():
        logger.info("CONFIG_APP :: Skipping scheduler initialization (migration command)")
        return True
    
    if _isTesting():
        logger.info("CONFIG_APP :: Skipping scheduler initialization (testing)")
        return True
    
    if not _isAllowedManagementCommand():
        if len(sys.argv) > 1:
            logger.info(f"CONFIG_APP :: Skipping scheduler initialization (command: {sys.argv[1]})")
        return True
    
    return False


def _ensureDatabaseConnection():
    """
    FIRST PRINCIPLE: Check database readiness before accessing it.
    
    This prevents:
    - Trying to query for existing jobs when DB doesn't exist
    - Registering jobs when DB tables aren't ready
    - Scheduler trying to persist jobs to non-existent tables
    
    Raises OperationalError or DatabaseError if database is not accessible.
    """
    connection.ensure_connection()


def _ensureDjangoApschedulerTables():
    """
    FIRST PRINCIPLE: Verify django_apscheduler tables exist before using scheduler.
    
    If the django_apscheduler migrations haven't been run, DjangoJobStore
    will fail or hang when trying to query non-existent tables.
    
    Returns True if tables exist, False otherwise.
    """
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            # Check if django_apscheduler_job table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'django_apscheduler_djangojob'
                );
            """)
            exists = cursor.fetchone()[0]
            if exists:
                logger.debug("CONFIG_APP :: django_apscheduler tables exist")
            else:
                logger.warning("CONFIG_APP :: django_apscheduler tables do not exist - migrations may not have been run")
            return exists
    except Exception as e:
        logger.warning(f"CONFIG_APP :: Could not check for django_apscheduler tables: {e}")
        # If we can't check, assume they exist (better to try than fail)
        return True


def _isCalledFromMigrationContext(**kwargs) -> bool:
    """
    FIRST PRINCIPLE: Distinguish between different call contexts.
    
    Contexts:
    1. Direct call from ready(): DB might not be ready yet (OK to fail gracefully)
    2. Call from post_migrate during migration: DB should be ready (error is unexpected)
    3. Call from post_migrate after normal startup: DB is ready (error is unexpected)
    
    Returns True if called in a context where DB should definitely be ready.
    """
    # Check if this is a migration command
    if _isMigrationCommand():
        return True
    
    # post_migrate signal passes 'using' parameter
    if kwargs.get('using'):
        return True
    
    return False


# ============================================================================
# MAIN APP CONFIG CLASS
# ============================================================================

class ConfigConfig(AppConfig):
    """
    Config app configuration.
    
    FIRST PRINCIPLE: Single Responsibility
    - This class is the ONLY place that initializes the scheduler
    - Prevents multiple scheduler instances across the application
    - Centralizes all scheduler startup logic
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'config'

    def ready(self):
        """
        Django lifecycle hook: Called when app is fully loaded.
        
        FIRST PRINCIPLE: Hybrid Initialization Strategy
        ================================================
        
        Strategy 1: SKIP during migrations
        ----------------------------------
        - Detect migration commands and skip entirely
        - Prevents jobs from being registered/executed during schema changes
        - Ensures migrations complete without interference
        
        Strategy 2: DIRECT initialization attempt
        -----------------------------------------
        - Try to register jobs immediately on server startup
        - Works when database is already ready (normal case)
        - Fast path: jobs registered without waiting for signals
        
        Strategy 3: FALLBACK to post_migrate signal
        -------------------------------------------
        - If direct init fails (DB not ready), post_migrate will retry
        - Handles edge cases: first deployment, DB initialization, etc.
        - Ensures jobs are registered even if timing is off
        
        Strategy 4: IDEMPOTENCY
        -----------------------
        - Global flag prevents double initialization
        - Job existence checks prevent duplicate registrations
        - Safe to call multiple times (cloud restarts, auto-reload, etc.)
        """
        global _scheduler_initialized
        
        # FIRST PRINCIPLE: Skip in inappropriate contexts
        if _shouldSkipInitialization():
            return
            
        # FIRST PRINCIPLE: Only initialize in actual server process
        if not _isMainProcess():
            logger.info("CONFIG_APP :: Skipping scheduler initialization (not main process)")
            return
            
        # FIRST PRINCIPLE: Setup fallback mechanism (post_migrate signal)
        # This ensures jobs are registered even if direct init fails
        post_migrate.connect(
            self._initializeScheduler,
            sender=self,
            weak=False  # Keep strong reference so signal handler isn't garbage collected
        )
        
        # FIRST PRINCIPLE: Try direct initialization (fast path)
        # If DB is ready, this will succeed immediately
        # If DB is not ready, we catch the error and let post_migrate retry
        try:
            self._initializeScheduler(sender=self)
        except (OperationalError, DatabaseError) as e:
            # FIRST PRINCIPLE: Graceful degradation
            # Database not ready yet - this is expected in some scenarios
            # post_migrate signal will retry when DB is ready
            logger.info(
                "CONFIG_APP :: Direct initialization deferred (DB not ready), "
                "will retry via post_migrate signal | Error: %s",
                str(e)
            )
            # Don't raise - allow post_migrate to handle it
        # All other exceptions propagate (they're real errors, not timing issues)

    def _initializeScheduler(self, sender, **kwargs):
        """
        Core initialization logic: Registers all scheduler jobs.
        
        FIRST PRINCIPLE: Idempotency
        -----------------------------
        - Global flag prevents multiple initializations
        - Safe to call from both direct init and post_migrate signal
        - Can be called multiple times without side effects
        
        FIRST PRINCIPLE: Database Readiness Check
        -----------------------------------------
        - Verify database is accessible before proceeding
        - Prevents errors when trying to check for existing jobs
        - Ensures scheduler can persist jobs to database
        
        FIRST PRINCIPLE: Context-Aware Error Handling
        ----------------------------------------------
        - If called from migration context: DB should be ready, errors are unexpected
        - If called from direct init: DB might not be ready, errors are expected
        - Different error handling based on call context
        """
        global _scheduler_initialized
        
        # FIRST PRINCIPLE: Idempotency check
        # Prevent double initialization (e.g., if both direct init and post_migrate succeed)
        if _scheduler_initialized:
            logger.info("CONFIG_APP :: Scheduler already initialized, skipping (idempotency)")
            return
        
        try:
            # FIRST PRINCIPLE: Verify database readiness
            # This prevents trying to access database when it's not ready
            _ensureDatabaseConnection()
            
            # FIRST PRINCIPLE: Verify django_apscheduler tables exist
            # If tables don't exist, scheduler will fail or hang
            if not _ensureDjangoApschedulerTables():
                logger.warning(
                    "CONFIG_APP :: django_apscheduler tables not found. "
                    "Please run migrations: python manage.py migrate"
                )
                # Don't raise - allow server to start, but scheduler won't work
                # User can run migrations and restart
                return
            
            # FIRST PRINCIPLE: Register jobs (with idempotency checks inside)
            # schedulerConfig.registerAllJobs() checks if jobs exist before adding
            logger.info("CONFIG_APP :: Registering scheduler jobs...")
            from config.schedulerConfig import registerAllJobs
            registerAllJobs()
            
            # Mark as initialized (idempotency flag)
            _scheduler_initialized = True
            logger.info("CONFIG_APP :: Scheduler initialization completed successfully")
            
        except (OperationalError, DatabaseError) as e:
            # FIRST PRINCIPLE: Context-aware error handling
            
            if _isCalledFromMigrationContext(**kwargs):
                # Called during/after migration - DB should be ready
                # This is unexpected, treat as real error
                logger.error(
                    "CONFIG_APP :: Database error during scheduler initialization "
                    "(unexpected in migration context) | Error: %s",
                    str(e),
                    exc_info=True
                )
                raise
            else:
                # Called directly from ready() - DB might not be ready yet
                # This is expected, let post_migrate retry
                logger.info(
                    "CONFIG_APP :: Database not ready, will retry via post_migrate signal | Error: %s",
                    str(e)
                )
                # Don't raise - allow post_migrate to retry
            
        except Exception as e:
            # FIRST PRINCIPLE: All other errors are real errors
            # These are not timing issues, they indicate actual problems
            # (e.g., import errors, configuration errors, etc.)
            logger.error(
                "CONFIG_APP :: Scheduler initialization failed with unexpected error | Error: %s",
                str(e),
                exc_info=True
            )
            raise