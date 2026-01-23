import os
import shutil
import logging
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# Add project root to sys.path to allow for absolute imports from the project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config.config import DATABASE_URL
from config.storage import get_storage_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _get_source_db_path() -> Path:
    """Parse DATABASE_URL and return the path to the source SQLite database."""
    db_url = urlparse(DATABASE_URL)
    
    if db_url.scheme != 'sqlite':
        logger.warning(f"Database operations currently only support SQLite. Found: {db_url.scheme}")
        return None
        
    # Accommodate different path representations in the DATABASE_URL
    db_path_str = db_url.path
    if db_path_str.startswith('/') and os.name == 'nt':  # For Windows systems
        db_path_str = db_path_str[1:]
        
    db_path = Path(db_path_str)
    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found at: {db_path}")
        
    return db_path


def create_archived_backup(backup_dir: str = None) -> str:
    """
    Creates a timestamped backup of the database file in the archive directory.
    
    This backup is for historical purposes and includes a timestamp in the filename.
    
    Args:
        backup_dir (str, optional): Directory to store backups. If None, uses BACKUP_DIRECTORY from config.
        
    Returns:
        str: Path to the created backup file, or None on failure.
    """
    try:
        source_path = _get_source_db_path()
        if not source_path:
            return None

        # Get the backup directory from config if not provided
        if backup_dir is None:
            config = get_storage_config()
            if 'backup_directory' not in config:
                raise ValueError("Backup directory not configured in storage config")
            backup_dir = config['backup_directory']
        
        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{source_path.stem}_backup_{timestamp}{source_path.suffix}"
        backup_filepath = backup_path / backup_filename
        
        # Create the backup
        shutil.copy2(source_path, backup_filepath)
        
        logger.info(f"Database archive backup created successfully at: {backup_filepath}")
        return str(backup_filepath)
        
    except Exception as e:
        logger.error(f"Failed to create archived database backup: {e}")
        raise


def update_public_db_copy(public_dir: str = None) -> str:
    """
    Copies the database to a public location, overwriting any existing file.
    
    This copy is intended for public access and consumption.
    
    Args:
        public_dir (str, optional): The public directory. If None, uses PUBLIC_DATABASE env var.

    Returns:
        str: Path to the public copy, or None on failure.
    """
    try:
        source_path = _get_source_db_path()
        if not source_path:
            return None

        # Get the public directory from environment variable if not provided
        if public_dir is None:
            public_dir = os.environ.get("PUBLIC_DATABASE")
        
        if not public_dir:
            logger.warning("PUBLIC_DATABASE environment variable not set, skipping public copy")
            return None
            
        public_path = Path(public_dir)
        public_path.mkdir(parents=True, exist_ok=True)
        
        # Create the public copy path, overwriting if it exists
        public_db_path = public_path / source_path.name
        
        # Create the public copy
        shutil.copy2(source_path, public_db_path)
        
        logger.info(f"Public database copy created successfully at: {public_db_path}")
        return str(public_db_path)
        
    except Exception as e:
        logger.error(f"Failed to create public database copy: {e}")
        return None


def cleanup_old_backups(backup_dir: str = None, keep_last_n: int = 5):
    """
    Remove old backup files from the archive, keeping only the most recent N backups.
    
    Args:
        backup_dir (str, optional): Directory containing backup files. If None, uses config.
        keep_last_n (int): Number of most recent backups to keep.
    """
    try:
        # Get the backup directory from config if not provided
        if backup_dir is None:
            config = get_storage_config()
            if 'backup_directory' not in config:
                logger.warning("Backup directory not configured, skipping cleanup")
                return
            backup_dir = config['backup_directory']
            
        backup_path = Path(backup_dir)
        if not backup_path.exists():
            logger.warning(f"Backup directory does not exist: {backup_path}")
            return
            
        # Get all backup files and sort by modification time
        backup_files = sorted(
            list(backup_path.glob("*_backup_*.db")),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        # Remove old backups
        if len(backup_files) > keep_last_n:
            for old_backup in backup_files[keep_last_n:]:
                old_backup.unlink()
                logger.info(f"Removed old backup: {old_backup}")
            
    except Exception as e:
        logger.error(f"Failed to cleanup old backups: {e}")


if __name__ == "__main__":
    try:
        logger.info("Starting manual database backup process...")
        
        # Create timestamped archive backup
        backup_file_path = create_archived_backup()
        if backup_file_path:
            logger.info(f"Manual archive backup successful: {backup_file_path}")
            
            # Clean up old archived backups
            logger.info("Cleaning up old backups...")
            cleanup_old_backups()
            logger.info("Old backups cleanup complete.")
        else:
            logger.warning("Archived backup process failed or was skipped.")
        
        # Update public database copy
        logger.info("Attempting to copy database to public location...")
        public_copy_path = update_public_db_copy()
        if public_copy_path:
            logger.info(f"Database copied to public location: {public_copy_path}")
        else:
            logger.info("Skipped or failed to copy database to public location.")
            
    except Exception as e:
        logger.error(f"An unexpected error occurred during the manual backup process: {e}")
