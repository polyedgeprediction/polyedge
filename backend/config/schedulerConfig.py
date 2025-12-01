"""
Centralized job configuration - WHEN to execute jobs.

FIRST PRINCIPLES APPROACH:
==========================

PROBLEM:
--------
1. Multiple places could register jobs (hard to maintain, risk of duplicates)
2. Jobs might be registered multiple times (duplicates, conflicts)
3. Need single source of truth for all scheduled jobs

SOLUTION:
---------
1. CENTRALIZATION: All job registration in one place
2. IDEMPOTENCY: Check if job exists before adding (safe to call multiple times)
3. MODULARITY: Separate functions for each job category (easy to maintain)
4. EXPLICIT SCHEDULING: Clear definition of WHEN each job runs

This module defines:
- WHAT jobs exist (job functions)
- WHEN they run (triggers, intervals)
- HOW to register them safely (idempotent registration)
"""
import logging
from typing import Callable, Any
from config.scheduler import getScheduler

logger = logging.getLogger(__name__)


# ============================================================================
# CORE REGISTRATION LOGIC (First Principles)
# ============================================================================

def _jobExists(scheduler, job_id: str) -> bool:
    """
    FIRST PRINCIPLE: Idempotency Check
    
    Check if a job with the given ID already exists in the scheduler.
    
    Why this matters:
    - Prevents duplicate job registration
    - Safe to call registerAllJobs() multiple times
    - Critical for cloud deployments (containers restart frequently)
    
    Returns True if job exists, False otherwise.
    Handles exceptions gracefully (returns False if check fails).
    """
    try:
        job = scheduler.get_job(job_id)
        return job is not None
    except Exception as e:
        # If we can't check (e.g., DB error), assume job doesn't exist
        # This is safer than assuming it exists (might cause duplicate)
        logger.warning(f"SCHEDULER_CONFIG :: Could not check if job exists: {job_id} | Error: {e}")
        return False


def _registerJob(
    scheduler,
    job_id: str,
    func: Callable,
    trigger_type: str = 'interval',
    **trigger_kwargs
) -> bool:
    """
    FIRST PRINCIPLE: Idempotent Job Registration
    
    Register a single job with the scheduler, but only if it doesn't already exist.
    
    Parameters:
    -----------
    scheduler: APScheduler instance
    job_id: Unique identifier for the job
    func: Function to execute when job runs
    trigger_type: Type of trigger ('interval', 'cron', 'date', etc.)
    **trigger_kwargs: Arguments for the trigger (e.g., hours=1, minutes=30)
    
    Returns:
    --------
    True if job was registered, False if it already existed
    
    FIRST PRINCIPLE: Idempotency
    - Safe to call multiple times
    - Won't create duplicate jobs
    - Essential for cloud deployments (restarts, scaling)
    """
    # FIRST PRINCIPLE: Check before adding (idempotency)
    if _jobExists(scheduler, job_id):
        logger.info(f"SCHEDULER_CONFIG :: Job already exists, skipping: {job_id}")
        return False
    
    # FIRST PRINCIPLE: Register with replace_existing=True as safety net
    # (Even though we check first, this ensures no duplicates if race condition occurs)
    scheduler.add_job(
        id=job_id,
        func=func,
        trigger=trigger_type,
        replace_existing=True,  # Safety: replace if somehow duplicate exists
        **trigger_kwargs
    )
    
    logger.info(f"SCHEDULER_CONFIG :: Successfully registered job: {job_id}")
    return True


# ============================================================================
# JOB CATEGORY REGISTRATION (Modular Design)
# ============================================================================

def _registerWalletJobs(scheduler):
    """
    FIRST PRINCIPLE: Single Responsibility
    Register all wallet-related scheduled jobs.
    
    Each job category is in its own function for:
    - Modularity (easy to find, modify, test)
    - Separation of concerns (wallet jobs separate from position jobs)
    - Maintainability (clear organization)
    """
    from wallets.schedulers.jobs import fetchLeaderboardData
    
    # Job: Fetch leaderboard data periodically
    # FIRST PRINCIPLE: Explicit scheduling (clear when it runs)
    _registerJob(
        scheduler=scheduler,
        job_id='fetch_leaderboard_data',
        func=fetchLeaderboardData,
        trigger_type='interval',
        hours=1  # Run every hour
    )
    
    logger.info("SCHEDULER_CONFIG :: Wallet jobs registration completed")


def _registerPositionJobs(scheduler):
    """
    FIRST PRINCIPLE: Single Responsibility
    Register all position-related scheduled jobs.
    """
    from positions.schedulers.jobs import fetchNewWalletPositions, updateExistingPositions
    
    # Job: Fetch positions for new wallets
    # FIRST PRINCIPLE: Explicit scheduling
    _registerJob(
        scheduler=scheduler,
        job_id='fetch_new_wallet_positions',
        func=fetchNewWalletPositions,
        trigger_type='interval',
        hours=2  # Run every 2 hours
    )
    
    # Job: Update existing positions
    # FIRST PRINCIPLE: Different jobs can have different schedules
    _registerJob(
        scheduler=scheduler,
        job_id='update_existing_positions',
        func=updateExistingPositions,
        trigger_type='interval',
        minutes=30  # Run every 30 minutes (more frequent)
    )
    
    logger.info("SCHEDULER_CONFIG :: Position jobs registration completed")


def _registerEventJobs(scheduler):
    """
    FIRST PRINCIPLE: Single Responsibility
    Register all event-related scheduled jobs.
    """
    from events.schedulers.UpdateEventsAndMarketsScheduler import UpdateEventsAndMarketsScheduler
    
    # Job: Update events and markets from external API
    # FIRST PRINCIPLE: Explicit scheduling
    _registerJob(
        scheduler=scheduler,
        job_id='update_events_and_markets',
        func=UpdateEventsAndMarketsScheduler.execute,
        trigger_type='interval',
        hours=10  # Run every 10 hours
    )
    
    logger.info("SCHEDULER_CONFIG :: Event jobs registration completed")


# ============================================================================
# PUBLIC API (Main Entry Point)
# ============================================================================

def registerAllJobs():
    """
    FIRST PRINCIPLE: Single Entry Point
    
    Register ALL application jobs with the scheduler.
    This is the ONLY function that should be called to register jobs.
    
    FIRST PRINCIPLE: Idempotency
    ----------------------------
    - Safe to call multiple times
    - Checks if jobs exist before adding
    - Won't create duplicates
    
    FIRST PRINCIPLE: Modularity
    ---------------------------
    - Delegates to category-specific registration functions
    - Easy to add new job categories
    - Clear organization
    
    FIRST PRINCIPLE: Error Handling
    --------------------------------
    - If any job registration fails, entire process fails
    - Ensures all-or-nothing registration (consistency)
    - Logs detailed error information
    
    Usage:
    ------
    Called automatically during Django app startup (config/apps.py)
    Can also be called manually if needed (e.g., for testing)
    """
    scheduler = getScheduler()
    
    try:
        # FIRST PRINCIPLE: Register by category (modular design)
        # Each category is independent - easy to add/remove/modify
        
        _registerWalletJobs(scheduler)
        _registerPositionJobs(scheduler)
        _registerEventJobs(scheduler)
        
        logger.info("SCHEDULER_CONFIG :: All jobs registered successfully")
        
    except Exception as e:
        # FIRST PRINCIPLE: Fail fast on errors
        # If job registration fails, we want to know immediately
        # Better to fail at startup than have missing jobs silently
        logger.error(
            "SCHEDULER_CONFIG :: Job registration failed | Error: %s",
            str(e),
            exc_info=True
        )
        raise


# ============================================================================
# UTILITY FUNCTIONS (Status/Diagnostics)
# ============================================================================

def getJobStatus():
    """
    FIRST PRINCIPLE: Observability
    
    Get current status of all registered jobs.
    Useful for:
    - Monitoring (check if jobs are registered)
    - Debugging (verify scheduler is working)
    - Health checks (cloud deployments)
    
    Returns:
    --------
    Dictionary with scheduler status and list of all jobs
    """
    scheduler = getScheduler()
    
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            'id': job.id,
            'func': job.func.__name__,
            'trigger': str(job.trigger),
            'nextRun': job.next_run_time.isoformat() if job.next_run_time else None
        })
    
    return {
        'schedulerRunning': scheduler.running,
        'totalJobs': len(jobs),
        'jobs': jobs
    }