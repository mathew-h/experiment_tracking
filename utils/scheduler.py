import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from .database_backup import create_archived_backup, cleanup_old_backups, update_public_db_copy

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None

def setup_backup_scheduler(
    backup_interval_hours=24,
    cleanup_interval_days=1,
    public_copy_interval_hours=12,
    keep_backups=30
):
    """
    Set up periodic database backups.
    
    Args:
        backup_interval_hours (int): Hours between backups
        cleanup_interval_days (int): Days between cleanup of old backups
        public_copy_interval_hours (int): Hours between public copies
        keep_backups (int): Number of backups to keep
    
    Returns:
        BackgroundScheduler: The initialized scheduler
    """
    global scheduler
    
    # Create scheduler if it doesn't exist
    if scheduler is None:
        scheduler = BackgroundScheduler()
        logger.info("Created new scheduler instance")
        
    elif scheduler.running:
        # If scheduler is already running, remove any existing backup jobs
        for job in scheduler.get_jobs():
            if job.id in ['database_backup', 'backup_cleanup', 'public_database_copy']:
                scheduler.remove_job(job.id)
                logger.info(f"Removed existing job: {job.id}")
    
    # Schedule database backup
    scheduler.add_job(
        func=lambda: create_archived_backup(),
        trigger=IntervalTrigger(hours=backup_interval_hours),
        id='database_backup',
        name=f'Database archive backup every {backup_interval_hours} hours',
        replace_existing=True
    )
    logger.info(f"Scheduled database archive backup job (every {backup_interval_hours} hours)")
    
    # Schedule cleanup of old backups
    scheduler.add_job(
        func=lambda: cleanup_old_backups(keep_last_n=keep_backups),
        trigger=IntervalTrigger(days=cleanup_interval_days),
        id='backup_cleanup',
        name=f'Clean up old backups every {cleanup_interval_days} days',
        replace_existing=True
    )
    logger.info(f"Scheduled backup cleanup job (every {cleanup_interval_days} days)")
    
    # Schedule public database copy
    scheduler.add_job(
        func=lambda: update_public_db_copy(),
        trigger=IntervalTrigger(hours=public_copy_interval_hours),
        id='public_database_copy',
        name=f'Public database copy every {public_copy_interval_hours} hours',
        replace_existing=True
    )
    logger.info(f"Scheduled public database copy job (every {public_copy_interval_hours} hours)")
    
    # Start the scheduler if it's not already running
    if not scheduler.running:
        scheduler.start()
        logger.info("Started scheduler")
    else:
        logger.info("Scheduler was already running, jobs have been updated")
    
    return scheduler

def shutdown_scheduler():
    """Shutdown the scheduler if it's running."""
    global scheduler
    
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("Shutdown scheduler")
        
def create_backup_now():
    """Create a database backup immediately."""
    try:
        backup_path = create_archived_backup()
        return backup_path
    except Exception as e:
        logger.error(f"Failed to create immediate backup: {str(e)}")
        return None

def create_public_copy_now():
    """Create a public database copy immediately."""
    try:
        public_path = update_public_db_copy()
        return public_path
    except Exception as e:
        logger.error(f"Failed to create immediate public copy: {str(e)}")
        return None
