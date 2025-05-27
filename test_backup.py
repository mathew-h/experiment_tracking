import logging
from utils.scheduler import create_backup_now

# Configure logging to show all messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting immediate database backup test...")
    
    try:
        backup_path = create_backup_now()
        if backup_path:
            logger.info(f"Backup created successfully at: {backup_path}")
        else:
            logger.error("Backup creation failed - no path returned")
    except Exception as e:
        logger.error(f"Backup creation failed with error: {str(e)}")

if __name__ == "__main__":
    main() 