"""
Trading Assistant Scheduler Service
Phase 5/6: Automation Foundation

Configures APScheduler with Europe/London timezone for unattended operations.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_SCHEDULER_STARTED, EVENT_SCHEDULER_SHUTDOWN
import logging
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Europe/London timezone for all scheduled operations
LONDON_TZ = ZoneInfo("Europe/London")

# Global scheduler instance
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler | None:
    """Get the global scheduler instance."""
    return _scheduler


def _on_scheduler_started(event):
    """Log when scheduler starts."""
    logger.info(f"Scheduler started successfully (timezone: {LONDON_TZ})")


def _on_scheduler_shutdown(event):
    """Log when scheduler shuts down."""
    logger.info("Scheduler shut down")


def init_scheduler() -> AsyncIOScheduler:
    """
    Initialize and configure the AsyncIOScheduler with Europe/London timezone.

    Returns:
        Configured AsyncIOScheduler instance ready to start.
    """
    global _scheduler

    if _scheduler is not None:
        logger.warning("Scheduler already initialized, returning existing instance")
        return _scheduler

    _scheduler = AsyncIOScheduler(
        timezone=LONDON_TZ,
        job_defaults={
            'coalesce': True,
            'max_instances': 1,
            'misfire_grace_time': 3600,
        }
    )

    _scheduler.add_listener(_on_scheduler_started, EVENT_SCHEDULER_STARTED)
    _scheduler.add_listener(_on_scheduler_shutdown, EVENT_SCHEDULER_SHUTDOWN)

    logger.info(f"Scheduler initialized with timezone: {LONDON_TZ}")
    return _scheduler


def start_scheduler() -> None:
    """Start the scheduler if not already running."""
    global _scheduler
    
    if _scheduler is None:
        raise RuntimeError("Scheduler not initialized. Call init_scheduler() first.")
    
    if not _scheduler.running:
        _scheduler.start()
        logger.info("Scheduler started")
    else:
        logger.debug("Scheduler already running")


def shutdown_scheduler(wait: bool = True) -> None:
    """
    Gracefully shut down the scheduler.
    
    Args:
        wait: If True, wait for jobs to complete before shutting down.
    """
    global _scheduler
    
    if _scheduler is None:
        logger.warning("Shutdown called but scheduler was never initialized")
        return
    
    if _scheduler.running:
        _scheduler.shutdown(wait=wait)
        logger.info(f"Scheduler shutdown (wait={wait})")
    else:
        logger.debug("Scheduler already stopped")
    
    _scheduler = None


def schedule_retention_job(
    job_func,
    hour: int = 2,
    minute: int = 0,
    job_id: str = "retention_cleanup"
) -> None:
    """
    Schedule the retention cleanup job to run at specified London time.
    
    Args:
        job_func: The async function to execute
        hour: Hour in 24-hour format (London time)
        minute: Minute (London time)
        job_id: Unique identifier for this job
    """
    global _scheduler
    
    if _scheduler is None:
        raise RuntimeError("Scheduler not initialized. Call init_scheduler() first.")
    
    # Remove existing job with same ID if present
    existing = _scheduler.get_job(job_id)
    if existing:
        _scheduler.remove_job(job_id)
        logger.info(f"Removed existing job: {job_id}")
    
    # Schedule with CronTrigger using London timezone
    _scheduler.add_job(
        job_func,
        trigger=CronTrigger(hour=hour, minute=minute, timezone=LONDON_TZ),
        id=job_id,
        name="Data Retention Cleanup",
        replace_existing=True,
    )
    
    logger.info(f"Scheduled retention job '{job_id}' for {hour:02d}:{minute:02d} London time")


def schedule_market_data_sync(
    job_func,
    hour: int = 8,
    minute: int = 0,
    job_id: str = "market_data_sync"
) -> None:
    """
    Schedule market data synchronization to run at specified London time.
    
    Args:
        job_func: The async function to execute
        hour: Hour in 24-hour format (London time)
        minute: Minute (London time)
        job_id: Unique identifier for this job
    """
    global _scheduler
    
    if _scheduler is None:
        raise RuntimeError("Scheduler not initialized. Call init_scheduler() first.")
    
    # Remove existing job with same ID if present
    existing = _scheduler.get_job(job_id)
    if existing:
        _scheduler.remove_job(job_id)
        logger.info(f"Removed existing job: {job_id}")
    
    # Schedule with CronTrigger using London timezone
    _scheduler.add_job(
        job_func,
        trigger=CronTrigger(hour=hour, minute=minute, timezone=LONDON_TZ),
        id=job_id,
        name="Market Data Sync",
        replace_existing=True,
    )
    
    logger.info(f"Scheduled market data sync job '{job_id}' for {hour:02d}:{minute:02d} London time")


def register_weekly_retention_job(job_func) -> None:
    """
    Register the retention cleanup job to run weekly on Sunday at 02:00 London time.

    Args:
        job_func: The async cleanup function (cleanup_old_logs from retention.py)
    """
    global _scheduler

    if _scheduler is None:
        raise RuntimeError("Scheduler not initialized. Call init_scheduler() first.")

    existing = _scheduler.get_job("weekly_retention_cleanup")
    if existing:
        _scheduler.remove_job("weekly_retention_cleanup")
        logger.info("Removed existing weekly retention job")

    _scheduler.add_job(
        job_func,
        trigger=CronTrigger(day_of_week="sun", hour=2, minute=0, timezone=LONDON_TZ),
        id="weekly_retention_cleanup",
        name="Weekly Data Retention Cleanup",
        replace_existing=True,
    )

    logger.info("Registered weekly retention cleanup job (Sundays 02:00 London time)")
