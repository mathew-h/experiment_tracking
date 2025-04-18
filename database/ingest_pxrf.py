"""
Script to ingest pXRF data from an Excel file into the database.
"""
import os
import sys
import pandas as pd
import numpy as np
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text
import argparse

# --- Adjust path to import from parent directory --- 
# Get the absolute path of the directory containing this script
script_dir = os.path.dirname(os.path.abspath(__file__))
# Get the absolute path of the parent directory (project root)
project_root = os.path.dirname(script_dir)
# Add the project root to the Python path
sys.path.insert(0, project_root)

# --- Database and Model Imports --- 
from database.database import engine, SessionLocal, init_db
from database.models import PXRFReading, ExternalAnalysis
from frontend.config.variable_config import PXRF_DATA_PATH, PXRF_REQUIRED_COLUMNS

# --- Configuration --- 
# Map Excel column names to model attribute names (case-sensitive)
COLUMN_MAP = {
    'Reading No': 'reading_no',
    'Fe': 'fe',
    'Mg': 'mg',
    'Ni': 'ni',
    'Cu': 'cu',
    'Si': 'si',
    'Co': 'co',
    'Mo': 'mo',
    'Al': 'al'
}

# Values to be treated as zero/null during numeric conversion
NULL_EQUIVALENTS = ['', '<LOD', 'LOD', 'ND', 'n.d.', 'n/a', 'N/A', None]

def find_matching_columns(df_columns, target_elements):
    """
    Find matching columns for each target element, accounting for variations in naming.
    
    Args:
        df_columns: List of column names from DataFrame
        target_elements: List of target element symbols
        
    Returns:
        dict: Mapping of target elements to found column names
    """
    matches = {}
    df_columns_lower = [col.lower().strip() for col in df_columns]
    
    for element in target_elements:
        # Try different variations of the element name
        variations = [
            element.lower(),           # e.g., 'fe'
            f"{element.lower()} %",    # e.g., 'fe %'
            f"{element.lower()}%",     # e.g., 'fe%'
            f"{element.lower()} ppm",  # e.g., 'fe ppm'
            f"{element.lower()}ppm",   # e.g., 'feppm'
        ]
        
        # Find the first matching variation
        for var in variations:
            if var in df_columns_lower:
                idx = df_columns_lower.index(var)
                matches[element.lower()] = df_columns[idx]  # Use original column name
                break
    
    return matches

# --- Ingestion Function --- 
def ingest_pxrf_data(file_path: str = PXRF_DATA_PATH, update_existing: bool = False):
    """
    Reads the pXRF Excel file, cleans data, and upserts into the PXRFReading table.

    Args:
        file_path (str): Path to the Excel file.
        update_existing (bool): If True, update existing entries. If False, skip them.
    """
    print(f"Starting pXRF data ingestion from: {file_path}")
    
    # Debug: Verify database connection and check existing data
    try:
        test_db = SessionLocal()
        test_db.execute(text("SELECT 1"))
        print("Database connection successful")
        
        # Debug: Show current readings in database
        existing_readings = test_db.query(PXRFReading).all()
        print(f"Current pXRF readings in database: {len(existing_readings)}")
        
        # Debug: Check external analyses that reference pXRF readings
        analyses_with_pxrf = test_db.query(ExternalAnalysis).filter(
            ExternalAnalysis.pxrf_reading_no.isnot(None)
        ).all()
        print(f"External analyses with pXRF references: {len(analyses_with_pxrf)}")
        for analysis in analyses_with_pxrf:
            print(f"Sample ID: {analysis.sample_id}, pXRF Reading No: {analysis.pxrf_reading_no}")
        
        test_db.close()
    except Exception as e:
        print(f"Database connection error: {e}")
        return

    # --- 1. Load Excel File --- 
    try:
        if not os.path.exists(file_path):
            print(f"Error: pXRF data file not found at {file_path}")
            return
            
        # Read the Excel file
        df = pd.read_excel(file_path)
        print("\nAnalyzing Excel file:")
        print("Available columns:", df.columns.tolist())
        
        # Check for required columns
        missing_columns = PXRF_REQUIRED_COLUMNS - set(df.columns)
        if missing_columns:
            print("\nError: Missing required columns:")
            print(missing_columns)
            print("\nPlease ensure your Excel file has these exact column names.")
            return
            
        print(f"\nSuccessfully loaded {len(df)} rows from Excel.")
        
        # Debug: Show first few rows of key columns
        print("\nFirst few rows of data:")
        print(df[list(PXRF_REQUIRED_COLUMNS)].head())
        
    except Exception as e:
        print(f"Error loading Excel file: {e}")
        return

    # --- 2. Clean Data --- 
    try:
        # Ensure Reading No is treated as string
        df['Reading No'] = df['Reading No'].astype(str).str.strip()
        
        # Remove rows with empty Reading No
        original_count = len(df)
        df = df.dropna(subset=['Reading No'])
        df = df[df['Reading No'] != '']
        if len(df) < original_count:
            print(f"\nRemoved {original_count - len(df)} rows with empty Reading No")
        
        # Clean numeric columns
        for col in PXRF_REQUIRED_COLUMNS - {'Reading No'}:
            # Replace null equivalents with 0
            df[col] = df[col].replace(NULL_EQUIVALENTS, 0)
            # Convert to numeric, coercing errors to NaN, then fill NaN with 0
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    except Exception as e:
        print(f"Error cleaning data: {e}")
        return

    # --- 3. Database Operations --- 
    db = SessionLocal()
    inserted_count = 0
    updated_count = 0
    skipped_count = 0

    try:
        print(f"\nProcessing {len(df)} rows for database insertion/update...")
        
        # Get existing reading numbers for faster lookup
        existing_reading_nos = set(row[0] for row in db.query(PXRFReading.reading_no).all())
        print(f"Found {len(existing_reading_nos)} existing readings in database")
        
        for _, row in df.iterrows():
            reading_no = row['Reading No']
            
            # Prepare data dictionary
            reading_data = {
                'reading_no': reading_no,
                'fe': row['Fe'],
                'mg': row['Mg'],
                'ni': row['Ni'],
                'cu': row['Cu'],
                'si': row['Si'],
                'co': row['Co'],
                'mo': row['Mo'],
                'al': row['Al']
            }
            
            if reading_no in existing_reading_nos:
                if update_existing:
                    # Update existing record
                    existing_record = db.query(PXRFReading).filter(PXRFReading.reading_no == reading_no).first()
                    for key, value in reading_data.items():
                        if key != 'reading_no':
                            setattr(existing_record, key, value)
                    updated_count += 1
                else:
                    skipped_count += 1
            else:
                # Insert new record
                new_reading = PXRFReading(**reading_data)
                db.add(new_reading)
                inserted_count += 1
                
        db.commit()
        print("Database commit successful")
        
        # Final verification
        final_count = db.query(PXRFReading).count()
        print(f"\nFinal verification: {final_count} total readings in database")
        
    except Exception as e:
        db.rollback()
        print(f"Error during database operation: {e}")
        print("Transaction rolled back.")
    finally:
        db.close()
        print("Database session closed.")

    print("\n--- Ingestion Summary ---")
    print(f"Total rows processed: {len(df)}")
    print(f"New readings inserted: {inserted_count}")
    print(f"Existing readings updated: {updated_count}")
    print(f"Existing readings skipped: {skipped_count}")
    print("-------------------------")

# --- Main Execution Guard --- 
if __name__ == "__main__":
    print("Running pXRF Ingestion Script...")
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Ingest pXRF data into the database.')
    parser.add_argument('--update-existing', action='store_true',
                      help='Update existing readings with new data')
    args = parser.parse_args()
    
    # Initialize database if needed
    init_db()
    
    # Use the parsed argument for update_existing
    ingest_pxrf_data(update_existing=args.update_existing)
    print("Script finished.") 