import os
import sys
import pandas as pd
import pytest

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Now import the modules
from frontend.components.pXRF_reader import (
    load_pxrf_data,
    get_pxrf_readings,
    get_element_averages,
    REQUIRED_COLUMNS,
    ELEMENT_COLUMNS
)
from frontend.config.variable_config import PXRF_DATA_PATH

def test_file_exists():
    """Test that the pXRF data file exists at the expected location"""
    print(f"\nLooking for file at: {PXRF_DATA_PATH}")
    print(f"Absolute path: {os.path.abspath(PXRF_DATA_PATH)}")
    assert os.path.exists(PXRF_DATA_PATH), f"pXRF data file not found at {PXRF_DATA_PATH}"

def test_file_readable():
    """Test that the Excel file can be read"""
    try:
        df = pd.read_excel(PXRF_DATA_PATH, engine='openpyxl')
        assert df is not None, "Failed to read Excel file"
    except Exception as e:
        pytest.fail(f"Error reading Excel file: {str(e)}")

def test_required_columns():
    """Test that all required columns are present in the Excel file"""
    df = pd.read_excel(PXRF_DATA_PATH, engine='openpyxl')
    missing_cols = REQUIRED_COLUMNS - set(df.columns)
    assert not missing_cols, f"Missing required columns: {missing_cols}"

def test_reading_no_format():
    """Test the format of Reading No column"""
    df = pd.read_excel(PXRF_DATA_PATH, engine='openpyxl')
    # Check if Reading No column exists
    assert 'Reading No' in df.columns, "Reading No column not found"
    
    # Print first few values to help diagnose
    print("\nFirst 5 Reading No values:")
    print(df['Reading No'].head())
    
    # Check if values are numeric or string
    print("\nReading No data type:", df['Reading No'].dtype)
    
    # Try to convert to string and check for any issues
    reading_nos = df['Reading No'].astype(str)
    print("\nUnique Reading No values:", reading_nos.unique())

def test_element_columns_format():
    """Test the format of element columns"""
    df = pd.read_excel(PXRF_DATA_PATH, engine='openpyxl')
    
    for element in ELEMENT_COLUMNS:
        print(f"\nTesting {element} column:")
        print(f"Data type: {df[element].dtype}")
        print(f"First 5 values: {df[element].head()}")
        print(f"Unique values: {df[element].unique()}")
        
        # Check for '<LOD' or other non-numeric values
        non_numeric = df[element].astype(str).str.contains('<LOD|LOD|ND|n.d.|n/a|N/A', case=False, na=False)
        if non_numeric.any():
            print(f"Found non-numeric values in {element}:")
            print(df[element][non_numeric].unique())

def test_specific_reading():
    """Test reading a specific known reading number"""
    # Try reading number 1
    readings_df = get_pxrf_readings("1")
    
    if readings_df is None:
        pytest.fail("Failed to get readings for Reading No 1")
    
    print("\nData for Reading No 1:")
    print(readings_df)
    
    # Check if we got the expected data
    assert not readings_df.empty, "No data found for Reading No 1"
    assert '1' in readings_df['Reading No'].values, "Reading No 1 not found in results"

def test_averages_calculation():
    """Test the calculation of element averages"""
    # Try calculating averages for reading 1
    averages = get_element_averages("1")
    
    if averages is None:
        pytest.fail("Failed to calculate averages for Reading No 1")
    
    print("\nAverages for Reading No 1:")
    print(averages)
    
    # Check if we got averages for all elements
    for element in ELEMENT_COLUMNS:
        assert element in averages, f"No average calculated for {element}"
        print(f"{element}: {averages[element]}")

if __name__ == "__main__":
    # Run tests and print detailed output
    print("Running pXRF reader tests...")
    
    # Run each test and print results
    test_file_exists()
    test_file_readable()
    test_required_columns()
    test_reading_no_format()
    test_element_columns_format()
    test_specific_reading()
    test_averages_calculation()
    
    print("\nAll tests completed. Check output above for any issues.") 