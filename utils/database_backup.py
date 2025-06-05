import os
import shutil
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from config import DATABASE_URL
from config.storage import get_storage_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def backup_database(backup_dir=None):
    """
    Create a backup of the database file.
    
    Args:
        backup_dir (str, optional): Directory where backups should be stored.
            If not provided, will use the backup_directory from storage config.
        
    Returns:
        str: Path to the created backup file
        
    Raises:
        ValueError: If database URL is invalid or backup fails
    """
    try:
        # Get the backup directory from config if not provided
        if backup_dir is None:
            config = get_storage_config()
            if 'backup_directory' not in config:
                raise ValueError("Backup directory not configured")
            backup_dir = config['backup_directory']
            
        # Clean up the backup directory path
        if isinstance(backup_dir, str):
            # Remove any raw string prefix (r"...") if present
            if backup_dir.startswith('r"') and backup_dir.endswith('"'):
                backup_dir = backup_dir[2:-1]
            # Remove any quotes if present
            backup_dir = backup_dir.strip('"\'')
            
        # Log the original backup directory for debugging
        logger.info(f"Original backup directory: {repr(backup_dir)}")
            
        # Parse database URL
        db_url = urlparse(DATABASE_URL)
        
        if db_url.scheme != 'sqlite':
            logger.warning(f"Database backup currently only supports SQLite databases. Found: {db_url.scheme}")
            logger.warning("For non-SQLite databases, please set up a proper backup solution using database tools.")
            return None
            
        # Get the database file path
        db_path = db_url.path
        if db_path.startswith('/'):
            db_path = db_path[1:]  # Remove leading slash for Windows compatibility
            
        if not os.path.exists(db_path):
            raise ValueError(f"Database file not found at: {db_path}")
            
        # Create backup directory if it doesn't exist
        try:
            # Use raw string handling to avoid escape sequence issues
            # Replace any problematic escape sequences with proper path separators
            if '\\x01' in repr(backup_dir):
                # The path has escape sequence issues, let's reconstruct it properly
                backup_dir = r"C:\Users\MathewHearl\Addis Energy\All Company - Addis Energy\01_R&D\01_Experiment Tracking\98_Backend\DO NOT TOUCH DATABASE FILE"
                logger.info(f"Using corrected backup directory: {backup_dir}")
            
            backup_path = Path(backup_dir)
            logger.info(f"Final backup path: {backup_path}")
            
            # Create directory if it doesn't exist
            backup_path.mkdir(parents=True, exist_ok=True)
            
        except Exception as e:
            logger.error(f"Failed to create backup directory: {str(e)}")
            logger.error(f"Backup directory repr: {repr(backup_dir)}")
            raise ValueError(f"Failed to create backup directory: {str(e)}")
        
        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"experiments_backup_{timestamp}.db"
        backup_filepath = backup_path / backup_filename
        
        # Log the full backup path
        logger.info(f"Attempting to create backup at: {backup_filepath}")
        
        # Create the backup
        shutil.copy2(db_path, backup_filepath)
        
        logger.info(f"Database backup created successfully at: {backup_filepath}")
        return str(backup_filepath)
        
    except Exception as e:
        logger.error(f"Failed to create database backup: {str(e)}")
        raise ValueError(f"Database backup failed: {str(e)}")

def copy_to_public_location():
    """
    Create a copy of the database file in the public sharepoint location.
    This creates a public copy that users can interact with directly.
    
    The public location is specified by the PUBLIC_DATABASE environment variable.
    The database file will maintain the original name (experiments.db).
    
    Returns:
        str: Path to the public copy if successful, None otherwise
        
    Raises:
        ValueError: If the database URL is invalid or copy fails
    """
    try:
        # Get the public sharepoint directory from environment variable
        public_dir = os.environ.get("PUBLIC_DATABASE")
        if not public_dir:
            logger.warning("PUBLIC_DATABASE environment variable not set, skipping public copy")
            return None
            
        # Parse database URL to get the source file path
        db_url = urlparse(DATABASE_URL)
        
        if db_url.scheme != 'sqlite':
            logger.warning(f"Public database copy only supports SQLite databases. Found: {db_url.scheme}")
            return None
            
        # Get the database file path
        db_path = db_url.path
        if db_path.startswith('/'):
            db_path = db_path[1:]  # Remove leading slash for Windows compatibility
            
        if not os.path.exists(db_path):
            raise ValueError(f"Database file not found at: {db_path}")
            
        # Create target directory if it doesn't exist
        public_path = Path(public_dir)
        public_path.mkdir(parents=True, exist_ok=True)
        
        # Get the database filename from the path
        db_filename = Path(db_path).name
        # If no specific filename, use the default "experiments.db"
        if not db_filename or db_filename == '':
            db_filename = "experiments.db"
        
        # Create the public copy path
        public_db_path = public_path / db_filename
        
        # Create the public copy
        shutil.copy2(db_path, public_db_path)
        
        logger.info(f"Public database copy created successfully at: {public_db_path}")
        return str(public_db_path)
        
    except Exception as e:
        logger.error(f"Failed to create public database copy: {str(e)}")
        return None

def cleanup_old_backups(backup_dir=None, keep_last_n=5):
    """
    Remove old backup files, keeping only the most recent N backups.
    
    Args:
        backup_dir (str, optional): Directory containing backup files.
            If not provided, will use the backup_directory from storage config.
        keep_last_n (int): Number of most recent backups to keep
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
            logger.warning(f"Backup directory does not exist: {backup_dir}")
            return
            
        # Get all backup files and sort by modification time
        backup_files = sorted(
            [f for f in backup_path.glob("experiments_backup_*.db")],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        # Remove old backups
        for old_backup in backup_files[keep_last_n:]:
            old_backup.unlink()
            logger.info(f"Removed old backup: {old_backup}")
            
    except Exception as e:
        logger.error(f"Failed to cleanup old backups: {str(e)}")

if __name__ == "__main__":
    try:
        logger.info("Starting manual database backup process...")
        backup_file_path = backup_database()
        if backup_file_path:
            logger.info(f"Manual backup successful: {backup_file_path}")
            
            logger.info("Cleaning up old backups...")
            cleanup_old_backups()
            logger.info("Old backups cleanup complete.")
        else:
            logger.warning("Manual backup process completed but did not return a backup file path (this might be expected if backup is not supported for the DB type).")
        
        # Optional: Call copy_to_public_location if needed
        # logger.info("Attempting to copy database to public location...")
        # public_copy_path = copy_to_public_location()
        # if public_copy_path:
        #     logger.info(f"Database copied to public location: {public_copy_path}")
        # else:
        #     logger.info("Skipped or failed to copy database to public location.")
            
    except ValueError as ve:
        logger.error(f"Manual backup process failed: {ve}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during the manual backup process: {e}")
