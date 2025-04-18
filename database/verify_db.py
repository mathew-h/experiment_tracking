"""
Script to verify database connection and contents.
"""
import os
import sys

# Add project root to Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

from database.database import SessionLocal, init_db
from database.models import PXRFReading

def verify_database():
    """Verify database connection and show contents."""
    print("Verifying database connection and contents...")
    
    try:
        # Initialize database if needed
        init_db()
        
        # Create session
        db = SessionLocal()
        
        # Test connection
        db.execute("SELECT 1")
        print("Database connection successful")
        
        # Get all pXRF readings
        readings = db.query(PXRFReading).all()
        print(f"\nFound {len(readings)} pXRF readings:")
        
        for reading in readings:
            print(f"\nReading No: {reading.reading_no}")
            print(f"Fe: {reading.fe}")
            print(f"Mg: {reading.mg}")
            print(f"Ni: {reading.ni}")
            print(f"Cu: {reading.cu}")
            print(f"Si: {reading.si}")
            print(f"Co: {reading.co}")
            print(f"Mo: {reading.mo}")
            print(f"Al: {reading.al}")
            print(f"Ingested at: {reading.ingested_at}")
            print(f"Updated at: {reading.updated_at}")
            print("-" * 50)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    verify_database() 