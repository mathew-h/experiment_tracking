import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from .database_backup import backup_database, cleanup_old_backups, copy_to_public_location

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None

def setup_backup_scheduler(
    backup_interval_hours=48,
    cleanup_interval_days=5,
    public_copy_interval_hours=12,
    keep_backups=5
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
        
    elif scheduler.running:
        # If scheduler is already running, remove any existing backup jobs
        for job in scheduler.get_jobs():
            if job.id in ['database_backup', 'backup_cleanup', 'public_database_copy']:
                scheduler.remove_job(job.id)
    
    # Schedule database backup
    scheduler.add_job(
        func=lambda: backup_database(),
        trigger=IntervalTrigger(hours=backup_interval_hours),
        id='database_backup',
        name=f'Database backup every {backup_interval_hours} hours',
        replace_existing=True
    )
    
    # Schedule cleanup of old backups
    scheduler.add_job(
        func=lambda: cleanup_old_backups(keep_last_n=keep_backups),
        trigger=IntervalTrigger(days=cleanup_interval_days),
        id='backup_cleanup',
        name=f'Clean up old backups every {cleanup_interval_days} days',
        replace_existing=True
    )
    
    # Schedule public database copy
    scheduler.add_job(
        func=lambda: copy_to_public_location(),
        trigger=IntervalTrigger(hours=public_copy_interval_hours),
        id='public_database_copy',
        name=f'Public database copy every {public_copy_interval_hours} hours',
        replace_existing=True
    )
    
    # Start the scheduler if it's not already running
    if not scheduler.running:
        scheduler.start()
        logger.info(f"Started database backup scheduler (every {backup_interval_hours} hours)")
        logger.info(f"Started public database copy scheduler (every {public_copy_interval_hours} hours)")
    else:
        logger.info(f"Updated database backup scheduler (every {backup_interval_hours} hours)")
        logger.info(f"Updated public database copy scheduler (every {public_copy_interval_hours} hours)")
    
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
        backup_path = backup_database()
        return backup_path
    except Exception as e:
        logger.error(f"Failed to create immediate backup: {str(e)}")
        return None

def create_public_copy_now():
    """Create a public database copy immediately."""
    try:
        public_path = copy_to_public_location()
        return public_path
    except Exception as e:
        logger.error(f"Failed to create immediate public copy: {str(e)}")
        return None
