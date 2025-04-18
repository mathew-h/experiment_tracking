import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import inspect
from typing import Dict, List, Optional, Tuple, Any
import logging
from .models import (
    Experiment,
    ExperimentalConditions,
    ExperimentalResults,
    SampleInfo,
    ExperimentStatus,
    ExternalAnalysis,
    ModificationsLog,
    ExperimentNotes,
    PXRFReading,
    ResultFiles,
    SamplePhotos,
    AnalysisFiles,
    Base
)
from .database import SessionLocal

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataValidationError(Exception):
    """Custom exception for data validation errors"""
    pass

def setup_logging(log_file: str = "data_ingestion.log"):
    """Configure logging to both file and console"""
    file_handler = logging.FileHandler(log_file)
    console_handler = logging.StreamHandler()
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

def get_model_columns(model: Base) -> Dict[str, Any]:
    """Get column names and their types from SQLAlchemy model"""
    mapper = inspect(model)
    columns = {}
    for column in mapper.columns:
        # Skip auto-generated columns
        if column.name not in ['created_at', 'updated_at', 'id']:
            columns[column.name] = column.type.python_type
    return columns

def get_model_for_sheet(sheet_name: str) -> Optional[Base]:
    """Map sheet names to SQLAlchemy models"""
    model_map = {
        'experiments': Experiment,
        'experimental_conditions': ExperimentalConditions,
        'experimental_results': ExperimentalResults,
        'sample_info': SampleInfo,
        'external_analyses': ExternalAnalysis,
        'modifications_log': ModificationsLog,
        'experiment_notes': ExperimentNotes,
        'pxrf_readings': PXRFReading,
        'result_files': ResultFiles,
        'sample_photos': SamplePhotos,
        'analysis_files': AnalysisFiles
    }
    return model_map.get(sheet_name.lower())

def validate_sheet_structure(df: pd.DataFrame, model: Base) -> List[str]:
    """Validate that the dataframe matches the model structure"""
    model_columns = get_model_columns(model)
    
    # Get required columns (non-nullable columns from the model)
    mapper = inspect(model)
    required_columns = [
        col.name for col in mapper.columns 
        if not col.nullable 
        and col.name not in ['id', 'created_at', 'updated_at']
    ]
    
    missing_columns = [col for col in required_columns if col not in df.columns]
    return missing_columns

def validate_experiment_ids(sheets_data: Dict[str, Tuple[pd.DataFrame, List[str]]]) -> List[str]:
    """Validate experiment_id consistency across sheets"""
    errors = []
    
    # Get experiment_ids from main experiments sheet
    if 'experiments' not in sheets_data:
        return ["Missing 'experiments' sheet"]
    
    experiments_df, _ = sheets_data['experiments']
    if experiments_df is None:
        return ["Invalid 'experiments' sheet"]
    
    valid_experiment_ids = set(experiments_df['experiment_id'].astype(str))
    
    # Check other sheets that should reference experiment_id
    related_sheets = ['experimental_conditions', 'experimental_results', 'experiment_notes', 'modifications_log']
    
    for sheet_name in related_sheets:
        if sheet_name not in sheets_data:
            continue
            
        df, _ = sheets_data[sheet_name]
        if df is None or 'experiment_id' not in df.columns:
            continue
            
        sheet_experiment_ids = set(df['experiment_id'].astype(str))
        invalid_ids = sheet_experiment_ids - valid_experiment_ids
        
        if invalid_ids:
            errors.append(f"Invalid experiment_ids in {sheet_name} sheet: {', '.join(invalid_ids)}")
    
    return errors

def validate_data_types(df: pd.DataFrame, model: Base) -> List[Tuple[str, str]]:
    """Validate data types against model column types"""
    type_errors = []
    model_columns = get_model_columns(model)
    
    for column, expected_type in model_columns.items():
        if column not in df.columns:
            continue
        
        try:
            if expected_type in (float, int):
                # Allow empty cells for nullable columns
                non_null_mask = df[column].notna()
                if non_null_mask.any():
                    pd.to_numeric(df[column][non_null_mask], errors='raise')
            elif expected_type == datetime:
                non_null_mask = df[column].notna()
                if non_null_mask.any():
                    pd.to_datetime(df[column][non_null_mask], errors='raise')
            elif expected_type == str:
                # Convert to string, but allow None/NaN
                df[column] = df[column].astype(str).replace('nan', None)
            elif expected_type == bool:
                non_null_mask = df[column].notna()
                if non_null_mask.any():
                    df[column][non_null_mask].astype(bool)
        except Exception as e:
            type_errors.append((column, str(e)))
    
    return type_errors

def process_enum_values(value: Any, column_type: Any) -> Any:
    """Process enum values from string to enum type"""
    if hasattr(column_type, 'python_type') and column_type.python_type == ExperimentStatus:
        if pd.isna(value):
            return None
        return map_experiment_status(str(value))
    return value

def map_experiment_status(status_str: str) -> ExperimentStatus:
    """Map string status to ExperimentStatus enum"""
    status_map = {
        'PLANNED': ExperimentStatus.PLANNED,
        'IN_PROGRESS': ExperimentStatus.IN_PROGRESS,
        'COMPLETED': ExperimentStatus.COMPLETED,
        'FAILED': ExperimentStatus.FAILED,
        'CANCELLED': ExperimentStatus.CANCELLED
    }
    
    status_str = str(status_str).upper()
    if status_str not in status_map:
        raise DataValidationError(f"Invalid status: {status_str}")
    
    return status_map[status_str]

def load_excel_data(file_path: str) -> Dict[str, Tuple[Optional[pd.DataFrame], List[str]]]:
    """Load and validate all sheets from Excel file"""
    try:
        excel_file = pd.ExcelFile(file_path)
        sheets_data = {}
        
        # First pass: Load all sheets and validate structure
        for sheet_name in excel_file.sheet_names:
            logger.info(f"Processing sheet: {sheet_name}")
            
            model = get_model_for_sheet(sheet_name)
            if not model:
                logger.warning(f"No corresponding model found for sheet: {sheet_name}")
                continue
            
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            
            # Convert empty strings to None
            df = df.replace(r'^\s*$', None, regex=True)
            
            # Validate structure
            missing_columns = validate_sheet_structure(df, model)
            if missing_columns:
                sheets_data[sheet_name] = (None, [f"Missing required columns in {sheet_name}: {', '.join(missing_columns)}"])
                continue
            
            # Validate data types
            type_errors = validate_data_types(df, model)
            if type_errors:
                sheets_data[sheet_name] = (None, [f"Data type error in {sheet_name}, column {col}: {err}" 
                                                for col, err in type_errors])
                continue
            
            sheets_data[sheet_name] = (df, [])
        
        # Second pass: Validate relationships
        relationship_errors = validate_experiment_ids(sheets_data)
        if relationship_errors:
            return {'error': (None, relationship_errors)}
        
        return sheets_data
        
    except Exception as e:
        return {'error': (None, [f"Error loading Excel file: {str(e)}"])}

def create_model_instance(row: pd.Series, model: Base) -> Base:
    """Create a model instance from a dataframe row"""
    model_columns = get_model_columns(model)
    data = {}
    
    for column, value in row.items():
        if column in model_columns:
            if pd.isna(value):
                data[column] = None
            else:
                column_type = inspect(model).columns[column].type
                data[column] = process_enum_values(value, column_type)
    
    return model(**data)

def import_data_to_db(sheets_data: Dict[str, Tuple[pd.DataFrame, List[str]]], db: Session):
    """Import validated data into the database"""
    try:
        # Process sheets in order of dependencies
        sheet_order = [
            'sample_info',
            'experiments',
            'experimental_conditions',
            'experimental_results',
            'external_analyses',
            'pxrf_readings',
            'result_files',
            'sample_photos',
            'analysis_files',
            'experiment_notes',
            'modifications_log'
        ]
        
        # Track created experiment_ids for relationship mapping
        experiment_map = {}
        
        for sheet_name in sheet_order:
            if sheet_name not in sheets_data:
                continue
                
            df, errors = sheets_data[sheet_name]
            if errors or df is None:
                continue
                
            model = get_model_for_sheet(sheet_name)
            logger.info(f"Importing data for {sheet_name}")
            
            for _, row in df.iterrows():
                instance = create_model_instance(row, model)
                
                # Special handling for experiments to track IDs
                if model == Experiment:
                    experiment_map[instance.experiment_id] = instance
                
                db.add(instance)
                
            db.flush()  # Flush after each sheet to establish relationships
            
        db.commit()
        logger.info("Data import completed successfully")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error during database import: {str(e)}")
        raise

def main():
    setup_logging()
    
    excel_file = Path("data/20250404_Master Data Migration Sheet.xlsx")
    
    if not excel_file.exists():
        logger.error(f"Excel file not found: {excel_file}")
        return
    
    sheets_data = load_excel_data(str(excel_file))
    
    has_errors = False
    for sheet_name, (df, errors) in sheets_data.items():
        if errors:
            has_errors = True
            logger.error(f"\nErrors in sheet {sheet_name}:")
            for error in errors:
                logger.error(f"  - {error}")
    
    if has_errors:
        logger.error("\nPlease fix the errors in the Excel file and try again.")
        return
    
    db = SessionLocal()
    try:
        import_data_to_db(sheets_data, db)
        logger.info("Data migration completed successfully")
    except Exception as e:
        logger.error(f"Failed to import data: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    main() 