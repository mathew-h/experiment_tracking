import os
from dotenv import load_dotenv
from urllib.parse import urlparse

# Load environment variables
load_dotenv()

# Database configuration
if "DATABASE_URL" not in os.environ:
    raise ValueError("DATABASE_URL environment variable must be set")

DATABASE_URL = os.environ["DATABASE_URL"]

# Validate database URL format
try:
    result = urlparse(DATABASE_URL)
    if not all([result.scheme, result.netloc or result.path]):
        raise ValueError("Invalid DATABASE_URL format")
    if result.scheme not in ['postgresql', 'mysql', 'sqlite', 'oracle', 'mssql']:
        raise ValueError(f"Unsupported database type: {result.scheme}")
except Exception as e:
    raise ValueError(f"Invalid DATABASE_URL: {str(e)}")

# Application configuration
APP_NAME = "Addis Energy Research"
APP_ICON = "frontend/static/Addis_Avatar_SandColor_NoBackground.png"  # Relative path to the icon
APP_LAYOUT = "wide" 

# Database connection arguments
DB_CONNECT_ARGS = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {} 