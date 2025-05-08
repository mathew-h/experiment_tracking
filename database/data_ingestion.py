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
    NMRResults,
    ScalarResults,
    SampleInfo,
    ExperimentStatus,
    ResultType,
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
        'nmr_results': NMRResults,
        'scalar_results': ScalarResults,
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
    required_columns = []
    
    for col in mapper.columns:
        # Skip auto-generated columns and foreign key columns
        if (not col.nullable and 
            col.name not in ['id', 'created_at', 'updated_at'] and
            not col.foreign_keys and  # Skip foreign key columns
            not col.name.endswith('_fk')):  # Also skip columns ending with _fk
            required_columns.append(col.name)
    
    # For related tables, require the human-readable ID instead of FK
    if model == ExperimentalConditions:
        required_columns.append('experiment_id')
    elif model == ExperimentalResults:
        required_columns.extend(['experiment_id', 'time_post_reaction'])
    elif model in [NMRResults, ScalarResults]:
        required_columns.extend(['experiment_id', 'time_post_reaction'])
    elif model == ExperimentNotes:
        required_columns.append('experiment_id')
    elif model == ResultFiles:
        required_columns.extend(['experiment_id', 'time_post_reaction'])
    
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
    related_sheets = [
        'experimental_conditions', 
        'experimental_results', 
        'experiment_notes', 
        'modifications_log',
        'nmr_results',
        'scalar_results'
    ]
    
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
    
    # Validate time_post_reaction references for NMR and Scalar results
    if 'experimental_results' in sheets_data:
        exp_results_df, _ = sheets_data['experimental_results']
        if exp_results_df is not None:
            exp_results_keys = set(zip(
                exp_results_df['experiment_id'].astype(str),
                exp_results_df['time_post_reaction']
            ))
            
            for sheet_name in ['nmr_results', 'scalar_results']:
                if sheet_name in sheets_data:
                    df, _ = sheets_data[sheet_name]
                    if df is not None:
                        result_keys = set(zip(
                            df['experiment_id'].astype(str),
                            df['time_post_reaction']
                        ))
                        invalid_keys = result_keys - exp_results_keys
                        if invalid_keys:
                            errors.append(
                                f"Invalid experiment_id/time_post_reaction combinations in {sheet_name}: "
                                f"{', '.join(f'({exp_id}, {time})' for exp_id, time in invalid_keys)}"
                            )
    
    return errors

def validate_result_type(value: Any) -> Optional[ResultType]:
    """Validate and convert result type string to ResultType enum"""
    if pd.isna(value):
        return None
    try:
        return ResultType[str(value).upper()]
    except KeyError:
        raise DataValidationError(f"Invalid result type: {value}. Must be one of {[t.name for t in ResultType]}")

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
            elif column == 'result_type' and model == ExperimentalResults:
                # Special handling for result_type validation
                non_null_mask = df[column].notna()
                if non_null_mask.any():
                    for value in df[column][non_null_mask]:
                        validate_result_type(value)
        except Exception as e:
            type_errors.append((column, str(e)))
    
    return type_errors

def process_enum_values(value: Any, column_type: Any) -> Any:
    """Process enum values from string to enum type"""
    if hasattr(column_type, 'python_type'):
        if column_type.python_type == ExperimentStatus:
            if pd.isna(value):
                return None
            return map_experiment_status(str(value))
        elif column_type.python_type == ResultType:
            return validate_result_type(value)
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
            
            df = pd.read_excel(excel_file, sheet_name=sheet_name, engine='openpyxl')
            
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

def create_model_instance(model_class, row_data, session):
    """Create a model instance from a dataframe row."""
    # Convert row data to dict, handling any non-string column names
    data_dict = {str(col): val for col, val in row_data.items()}
    
    # Create the model instance
    instance = model_class()
    
    # Set attributes from data_dict
    for col in model_class.__table__.columns:
        # Ensure column name exists in data_dict before trying to access
        if col.name in data_dict and pd.notna(data_dict[col.name]):
             # Process enums before setting attribute
            column_type = col.type
            value = process_enum_values(data_dict[col.name], column_type)
            setattr(instance, col.name, value)
    
    # Add the instance to the session early so it can be found by relationships
    session.add(instance)

    # --- Calculation Logic --- 
    # Calculations should happen *after* adding to session and potentially flushing,
    # ensuring the instance exists and relationships can be queried if needed.

    if model_class.__name__ == 'ExperimentalConditions':
        # Basic conditions might be needed by others, calculate early
        session.flush([instance]) # Flush only this instance to get IDs if needed
        instance.calculate_derived_conditions()

    elif model_class.__name__ == 'NMRResults':
        # NMR calculations might depend on conditions, but primarily internal
        session.flush([instance]) # Flush this instance
        # Ensure relationship to parent ExperimentalResults is loaded if needed for calculation
        # (calculate_values currently doesn't seem to need the parent explicitly, but good practice)
        # session.refresh(instance, attribute_names=['result_entry'])
        instance.calculate_values()
        
    elif model_class.__name__ == 'ScalarResults':
        # ScalarResults yield calculation DEPENDS on NMRResults and ExperimentalConditions
        session.flush([instance]) # Flush this instance to get its ID and establish FKs
        
        # Explicitly reload the instance and its required relationships from the session 
        # *after* flushing to ensure we get the latest state, including potentially 
        # calculated values from related objects added earlier in the transaction.
        session.refresh(instance, attribute_names=['result_entry'])
        if instance.result_entry:
             # Eagerly load relationships needed for calculate_yields
            session.refresh(instance.result_entry, attribute_names=['nmr_data', 'experiment'])
            if instance.result_entry.experiment:
                session.refresh(instance.result_entry.experiment, attribute_names=['conditions'])

        # Now, attempt the calculation with refreshed data
        instance.calculate_yields()
            
    # Note: We don't return the instance anymore as the primary purpose is adding/modifying in the session
    # The calling function `import_data_to_db` handles the overall session management (add, flush, commit).
    # return instance # Removed return

def import_data_to_db(sheets_data: Dict[str, Tuple[pd.DataFrame, List[str]]], db: Session):
    """Import validated data into the database"""
    # Cache Experiment IDs for quick lookup
    experiment_id_to_fk_map = {}
    if 'experiments' in sheets_data and sheets_data['experiments'][0] is not None:
        exp_df = sheets_data['experiments'][0]
        # Pre-fetch experiment IDs and their primary keys
        experiments = db.query(Experiment.id, Experiment.experiment_id).all()
        experiment_id_to_fk_map = {exp_id: pk for pk, exp_id in experiments}

    # Cache ExperimentalResults composite keys for NMR/Scalar lookup
    exp_results_key_to_id_map = {}
    if 'experimental_results' in sheets_data and sheets_data['experimental_results'][0] is not None:
        # Query existing ExperimentalResults to map (experiment_fk, time) -> result_id
        results = db.query(ExperimentalResults.id, ExperimentalResults.experiment_fk, ExperimentalResults.time_post_reaction).all()
        exp_results_key_to_id_map = {(fk, time): res_id for res_id, fk, time in results}

    try:
        # Process sheets in order of dependencies
        sheet_order = [
            'sample_info',          # Independent, no dependencies
            'experiments',          # Depends on sample_info
            'experimental_conditions',  # Depends on experiments
            'experimental_results',     # Depends on experiments
            'nmr_results',             # Depends on experimental_results (composite key)
            'scalar_results',          # Depends on experimental_results (composite key)
            'pxrf_readings',           # Independent, referenced by external_analyses
            'external_analyses',        # Depends on sample_info and references pxrf_readings
            'result_files',            # Depends on experimental_results
            'sample_photos',           # Depends on sample_info
            'analysis_files',          # Depends on external_analyses
            'experiment_notes',        # Depends on experiments
            'modifications_log'        # Depends on experiments
        ]
        
        for sheet_name in sheet_order:
            if sheet_name not in sheets_data:
                continue
                
            df, errors = sheets_data[sheet_name]
            if errors or df is None:
                continue
                
            model = get_model_for_sheet(sheet_name)
            logger.info(f"Importing data for {sheet_name}")
            
            if sheet_name in ['nmr_results', 'scalar_results']:
                for _, row in df.iterrows():
                    exp_id_str = str(row['experiment_id'])
                    time_post_reaction = row['time_post_reaction']
                    
                    # Find the corresponding Experiment FK from the cache
                    experiment_fk = experiment_id_to_fk_map.get(exp_id_str)
                    if experiment_fk is None:
                        logger.warning(f"Skipping {sheet_name} row: Cannot find Experiment FK for experiment_id {exp_id_str}")
                        continue

                    # Find the parent ExperimentalResults ID using the cached composite key
                    parent_result_id = exp_results_key_to_id_map.get((experiment_fk, time_post_reaction))
                    
                    if parent_result_id is None:
                        logger.warning(f"Skipping {sheet_name} row: Cannot find parent ExperimentalResults for experiment_id {exp_id_str}, time {time_post_reaction}")
                        continue
                        
                    # Create instance using the parent ID
                    data = row.to_dict()
                    data['result_id'] = parent_result_id
                    # Remove helper columns not in the model
                    data.pop('experiment_id', None)
                    data.pop('time_post_reaction', None)

                    # Prepare data dictionary for model creation, handling potential NaNs
                    model_columns = list(inspect(model).columns.keys()) # Get list of column names
                    instance_data = {}
                    for column, value in data.items():
                        if column in model_columns:
                            if pd.isna(value):
                                instance_data[column] = None
                            else:
                                # Get column type info directly from the model's columns
                                column_obj = inspect(model).columns.get(column)
                                if column_obj is not None:
                                     instance_data[column] = process_enum_values(value, column_obj.type)
                                else:
                                     # Handle case where column name from data doesn't match model exactly (log warning?)
                                     logger.warning(f"Column '{column}' found in data but not in model {model.__name__} columns.")
                    
                    # Call create_model_instance - it adds to session and calculates
                    create_model_instance(model, instance_data, db)
                    # No need to explicitly add instance = ... db.add(instance)
            else:
                 # Default handling for other sheets
                for _, row in df.iterrows():
                    # Prepare data dictionary, converting row to dict first
                    row_dict = row.to_dict()
                    # Ensure experiment_fk is set correctly for dependent tables
                    if 'experiment_id' in row_dict and hasattr(model, 'experiment_fk'):
                        exp_id_str = str(row_dict['experiment_id'])
                        experiment_fk = experiment_id_to_fk_map.get(exp_id_str)
                        if experiment_fk:
                            row_dict['experiment_fk'] = experiment_fk
                        else:
                             logger.warning(f"Missing Experiment FK for experiment_id {exp_id_str} in sheet {sheet_name}, row index {_}")
                             # Skip row if FK is essential and missing? Assuming FK is nullable or handled by DB constraints if not.
                             if not inspect(model).columns['experiment_fk'].nullable:
                                 logger.error(f"Skipping row index {_} in {sheet_name} due to missing non-nullable Experiment FK for {exp_id_str}")
                                 continue # Skip this row

                    # Call create_model_instance - it adds to session and calculates
                    create_model_instance(model, row_dict, db)
                    # No need to explicitly add instance = ... db.add(instance)
                
            # Consider flushing more strategically if needed, but flushing per sheet might be okay.
            db.flush()  # Flush after processing all rows in a sheet
            
            # Update caches after processing sheets that create new FKs
            if sheet_name == 'experiments':
                # Re-query all experiments after flushing this sheet
                experiments = db.query(Experiment.id, Experiment.experiment_id).all()
                experiment_id_to_fk_map = {exp_id: pk for pk, exp_id in experiments}
            elif sheet_name == 'experimental_results':
                # Re-query all results after flushing this sheet
                results = db.query(ExperimentalResults.id, ExperimentalResults.experiment_fk, ExperimentalResults.time_post_reaction).all()
                exp_results_key_to_id_map = {(fk, time): res_id for res_id, fk, time in results}

        db.commit()
        logger.info("Data import completed successfully")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error during database import: {str(e)}")
        raise

def main():
    setup_logging()
    
    excel_file = Path("data/data_ingestion_template.xlsx")
    
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