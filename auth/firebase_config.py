import firebase_admin
from firebase_admin import credentials, auth
import os
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Get Firebase credentials from environment variables
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")
FIREBASE_PRIVATE_KEY = os.getenv("FIREBASE_PRIVATE_KEY")
FIREBASE_CLIENT_EMAIL = os.getenv("FIREBASE_CLIENT_EMAIL")

# Client-side Firebase config
FIREBASE_CONFIG = {
    "apiKey": os.getenv("FIREBASE_API_KEY"),
    "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
    "projectId": FIREBASE_PROJECT_ID,
    "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
    "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
    "appId": os.getenv("FIREBASE_APP_ID"),
    "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID"),
}

# Initialize Firebase Admin SDK
try:
    # Check if Firebase is already initialized
    if not firebase_admin._apps:
        # Create credentials from environment variables
        cred_dict = {
            "type": "service_account",
            "project_id": FIREBASE_PROJECT_ID,
            "private_key": FIREBASE_PRIVATE_KEY.replace('\\n', '\n'),
            "client_email": FIREBASE_CLIENT_EMAIL,
            "client_id": os.getenv("FIREBASE_CLIENT_ID"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL")
        }
        
        # Initialize with credentials
        cred = credentials.Certificate(cred_dict)
        app = firebase_admin.initialize_app(cred)
        print("Firebase initialized successfully with environment credentials")
    else:
        app = firebase_admin.get_app()
        print("Using existing Firebase app")
except Exception as e:
    print(f"Error initializing Firebase: {str(e)}")
    raise

def verify_token(token):
    """Verify Firebase token (either ID token or custom token)."""
    try:
        # First try to verify as ID token
        try:
            decoded_token = auth.verify_id_token(token)
            return decoded_token
        except:
            # If ID token verification fails, try custom token
            decoded_token = auth.verify_id_token(token, check_revoked=False)
            return decoded_token
    except Exception as e:
        print(f"Error verifying token: {str(e)}")
        return None

def get_user_by_email(email):
    """Get user by email."""
    try:
        user = auth.get_user_by_email(email)
        return user
    except Exception as e:
        print(f"Error getting user by email: {str(e)}")
        return None

def get_firebase_config():
    """Get Firebase configuration for client-side."""
    return FIREBASE_CONFIG 