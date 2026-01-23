import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Storage configuration
STORAGE_TYPE = os.getenv("STORAGE_TYPE", "local")  # "local" or "s3" or "gcs" or "azure"
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET", "")
BACKUP_DIRECTORY = os.getenv("BACKUP_DIRECTORY", os.path.join(os.path.dirname(os.path.dirname(__file__)), "backups"))

# AWS S3 configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Google Cloud Storage configuration
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

# Azure Blob Storage configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
AZURE_STORAGE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER", "uploads")

def get_storage_config():
    """Get storage configuration based on environment."""
    if STORAGE_TYPE == "s3":
        return {
            "type": "s3",
            "bucket": STORAGE_BUCKET,
            "aws_access_key_id": AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": AWS_SECRET_ACCESS_KEY,
            "region": AWS_REGION,
            "backup_directory": BACKUP_DIRECTORY
        }
    elif STORAGE_TYPE == "gcs":
        return {
            "type": "gcs",
            "bucket": STORAGE_BUCKET,
            "project": GOOGLE_CLOUD_PROJECT,
            "credentials_path": GOOGLE_APPLICATION_CREDENTIALS,
            "backup_directory": BACKUP_DIRECTORY
        }
    elif STORAGE_TYPE == "azure":
        return {
            "type": "azure",
            "connection_string": AZURE_STORAGE_CONNECTION_STRING,
            "container": AZURE_STORAGE_CONTAINER,
            "backup_directory": BACKUP_DIRECTORY
        }
    else:
        return {
            "type": "local",
            "base_path": os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads"),
            "backup_directory": BACKUP_DIRECTORY
        } 