"""
Centralized job configuration - WHEN to execute jobs.
Single source of truth for ALL scheduled jobs.
"""
import logging
from config.scheduler import getScheduler

logger = logging.getLogger(__name__)


def registerAllJobs():
    """
    Register ALL application jobs with the scheduler.
    Called ONCE during application startup.
    """
    scheduler = getScheduler()
    
    try:
        # Wallet Jobs
        _registerWalletJobs(scheduler)
        
        # Position Jobs  
        _registerPositionJobs(scheduler)
        
        # Event Jobs
        _registerEventJobs(scheduler)
        
        logger.info("SCHEDULER_CONFIG :: All jobs registered successfully")
        
    except Exception as e:
        logger.error(
            "SCHEDULER_CONFIG :: Job registration failed | Error: %s",
            str(e),
            exc_info=True
        )
        raise


def _registerWalletJobs(scheduler):
    """Register wallet-related jobs"""
    from wallets.schedulers.jobs import fetchLeaderboardData
    
    # Fetch leaderboard data every hour
    scheduler.add_job(
        id='fetch_leaderboard_data',
        func=fetchLeaderboardData,
        trigger='interval',
        hours=1,
        replace_existing=True
    )
    
    logger.info("SCHEDULER_CONFIG :: Wallet jobs registered")


def _registerPositionJobs(scheduler):
    """Register position-related jobs"""
    from positions.schedulers.jobs import fetchNewWalletPositions, updateExistingPositions
    
    # Fetch new wallet positions every 2 hours
    scheduler.add_job(
        id='fetch_new_wallet_positions',
        func=fetchNewWalletPositions,
        trigger='interval',
        hours=2,
        replace_existing=True
    )
    
    # Update existing positions every 30 minutes
    scheduler.add_job(
        id='update_existing_positions',
        func=updateExistingPositions,
        trigger='interval',
        minutes=30,
        replace_existing=True
    )
    
    logger.info("SCHEDULER_CONFIG :: Position jobs registered")


def _registerEventJobs(scheduler):
    """Register event-related jobs"""
    from events.schedulers.UpdateEventsAndMarketsScheduler import UpdateEventsAndMarketsScheduler
    
    # Update events and markets every 10 hours
    scheduler.add_job(
        id='update_events_and_markets',
        func=UpdateEventsAndMarketsScheduler.execute,
        trigger='interval',
        hours=10,
        replace_existing=True
    )
    
    logger.info("SCHEDULER_CONFIG :: Event jobs registered")


def getJobStatus():
    """Get status of all registered jobs"""
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