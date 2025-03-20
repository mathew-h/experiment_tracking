import os
import sys

# Add the project root directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import Firebase config first to ensure initialization
from auth.firebase_config import get_firebase_config
from scripts.manage_users import main

if __name__ == '__main__':
    main() 