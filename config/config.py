import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///experiments.db")

# Application configuration
APP_NAME = "Addis Energy Research"
APP_ICON = "🧪"  # Using an emoji as fallback icon
APP_LAYOUT = "wide" 

# Database connection arguments
DB_CONNECT_ARGS = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {} 