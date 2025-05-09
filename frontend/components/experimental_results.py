import datetime
import streamlit as st
import os
import json
from sqlalchemy.orm import Session, selectinload # Import Session and selectinload for type hinting and eager loading
from database.database import SessionLocal
from database.models import (
    Experiment,
    ExperimentalResults,
    ResultFiles,
    ModificationsLog,
    ResultType,
    ScalarResults,
    NMRResults # Import NMRResults model
)
# Import utilities and config
from frontend.components.utils import log_modification, save_uploaded_file, delete_file_if_exists
from frontend.config.variable_config import SCALAR_RESULTS_CONFIG, NMR_RESULTS_CONFIG, RESULT_TYPE_FIELDS # Import the main config mapping

# TODO: Define a base class or interface for different result types (e.g., Scalar, pXRF, NMR)
# class BaseResultHandler:
#     def process(self, data):
#         raise NotImplementedError
#     def save(self, db, experiment_id, processed_data):
#         raise NotImplementedError

# TODO: Implement specific handlers for different result types inheriting from BaseResultHandler

# --- Helper function to save/update scalar data ---
def _save_or_update_scalar(db: Session, result: ExperimentalResults, scalar_data: dict):
    """Helper to save or update the ScalarResults associated with an ExperimentalResults entry."""
    scalar_entry = result.scalar_data
    old_values = {}
    new_values = {}

    if scalar_entry:
        # Updating existing scalar data
        modification_type = "update"
        for field_name in SCALAR_RESULTS_CONFIG.keys():
             # Skip time_post_reaction as it's on the parent result
             if field_name == 'time_post_reaction':
                  continue
             if hasattr(scalar_entry, field_name):
                  old_values[field_name] = getattr(scalar_entry, field_name)

        # Update fields from provided scalar_data dictionary
        for field_name, value in scalar_data.items():
             if field_name in SCALAR_RESULTS_CONFIG and hasattr(scalar_entry, field_name):
                  setattr(scalar_entry, field_name, value)
                  new_values[field_name] = value
    else:
        # Creating new scalar data
        modification_type = "create"
        scalar_kwargs = {'result_id': result.id}
        for field_name, config in SCALAR_RESULTS_CONFIG.items():
            if field_name == 'time_post_reaction': continue # Skip time
            # Get value from form data, fall back to config default
            value = scalar_data.get(field_name, config.get('default'))
            scalar_kwargs[field_name] = value
            new_values[field_name] = value

        scalar_entry = ScalarResults(**scalar_kwargs)
        db.add(scalar_entry)
        result.scalar_data = scalar_entry # Associate with the main result

    # TODO: Add call to calculate derived scalar values if needed
    # if hasattr(scalar_entry, 'calculate_derived_yields'):
    #    scalar_entry.calculate_derived_yields(db) # Might need db or other relationships
    #    # Update new_values log with calculated fields

    # Log the modification
    log_modification(
        db=db,
        experiment_id=result.experiment.experiment_id,
        modified_table=ScalarResults.__tablename__,
        modification_type=modification_type,
        old_values=old_values if old_values else None,
        new_values=new_values if new_values else None,
        related_id=result.id
    )
    return scalar_entry # Return the saved/updated entry

# --- Helper function to save/update primary result data ---
def _save_or_update_primary(db: Session, result: ExperimentalResults, primary_data: dict, primary_type: ResultType):
    """Helper to save or update primary result data (NMR, GC, etc.)."""
    if primary_type.name not in RESULT_TYPE_FIELDS:
        st.error(f"Configuration for result type '{primary_type.name}' not found.")
        raise ValueError(f"Invalid primary_type: {primary_type.name}") # Raise error to force rollback

    type_info = RESULT_TYPE_FIELDS[primary_type.name]
    primary_config = type_info['config']
    SpecificModel = None
    relationship_name = None

    # --- Determine Model and Relationship based on Primary Type ---
    # Example for NMR:
    if primary_type == ResultType.NMR:
        SpecificModel = NMRResults
        relationship_name = 'nmr_data'
    # --- Add elif blocks for other primary types (GC, PXRF, etc.) ---
    # elif primary_type == ResultType.GC:
    #     SpecificModel = GCResults
    #     relationship_name = 'gc_data'
    # elif primary_type == ResultType.PXRF:
    #     SpecificModel = PXRFResults # Assuming this model exists
    #     relationship_name = 'pxrf_data' # Assuming this relationship exists

    if not SpecificModel or not relationship_name:
        st.error(f"Model or relationship not defined for result type '{primary_type.name}'.")
        raise ValueError(f"Model/relationship undefined for {primary_type.name}")

    # --- Get or Create Specific Data Entry ---
    primary_entry = getattr(result, relationship_name)
    old_values = {}
    new_values = {}

    if primary_entry:
        # Updating existing primary data
        modification_type = "update"
        for field_name in primary_config.keys():
            if hasattr(primary_entry, field_name):
                old_values[field_name] = getattr(primary_entry, field_name)

        # Update fields
        for field_name, value in primary_data.items():
            if field_name in primary_config and hasattr(primary_entry, field_name):
                setattr(primary_entry, field_name, value)
                new_values[field_name] = value
    else:
        # Creating new primary data
        modification_type = "create"
        primary_kwargs = {'result_id': result.id} # Link to main result
        for field_name, config in primary_config.items():
            # Get value from form, fall back to config default
            value = primary_data.get(field_name, config.get('default'))
            primary_kwargs[field_name] = value
            new_values[field_name] = value

        primary_entry = SpecificModel(**primary_kwargs)
        db.add(primary_entry)
        setattr(result, relationship_name, primary_entry) # Associate with main result

    # --- Perform Calculations (if applicable for the primary type) ---
    if hasattr(primary_entry, 'calculate_values'):
        primary_entry.calculate_values()
        # Update new_values log with calculated fields
        for field_name in primary_config.keys():
             if hasattr(primary_entry, field_name):
                 calculated_value = getattr(primary_entry, field_name)
                 # Add to log if not an input or if value changed
                 if field_name not in primary_data or new_values.get(field_name) != calculated_value:
                      new_values[field_name] = calculated_value

    # Log the modification
    log_modification(
        db=db,
        experiment_id=result.experiment.experiment_id,
        modified_table=SpecificModel.__tablename__,
        modification_type=modification_type,
        old_values=old_values if old_values else None,
        new_values=new_values if new_values else None,
        related_id=result.id
    )
    return primary_entry # Return the saved/updated entry


# --- Main Save Function (Refactored) ---
def save_results(experiment_id, time_post_reaction, result_type, result_description, scalar_data, primary_data, uploaded_files_data=None, result_id_to_edit=None):
    """
    Save or update experiment results for a specific time point.
    Handles creation/update of ExperimentalResults, ScalarResults, and primary result data (NMR, GC, etc.).

    Args:
        experiment_id (int): The primary key (DB ID) of the experiment.
        time_post_reaction (float): Time in hours post-reaction.
        result_type (ResultType): The PRIMARY type of result being saved (Enum member, e.g., NMR).
        result_description (str): The description for this result entry.
        scalar_data (dict): Dictionary of scalar field values.
        primary_data (dict): Dictionary containing data for the primary result type.
        uploaded_files_data (list[dict], optional): List of file upload data.
        result_id_to_edit (int, optional): The ID of the ExperimentalResults entry to update.

    Returns:
        bool: True if save was successful, False otherwise.
    """
    db = SessionLocal()
    try:
        # --- Get or Create Main ExperimentalResults Entry ---
        if result_id_to_edit:
            # Editing existing entry - Load result and related data
            result = db.query(ExperimentalResults).options(
                selectinload(ExperimentalResults.scalar_data),
                selectinload(ExperimentalResults.nmr_data) # Add others as needed (gc_data, pxrf_data)
            ).filter(ExperimentalResults.id == result_id_to_edit).first()

            if not result:
                st.error(f"Result entry with ID {result_id_to_edit} not found for editing.")
                return False
            # Ensure the primary type matches (can't change type during edit)
            if result.result_type != result_type:
                 st.error(f"Cannot change primary result type during edit (Existing: {result.result_type.name}, Attempted: {result_type.name}).")
                 return False
            # Update description if it has changed
            if result.description != result_description:
                old_desc = result.description
                result.description = result_description
                log_modification(
                    db=db,
                    experiment_id=result.experiment.experiment_id,
                    modified_table=ExperimentalResults.__tablename__,
                    modification_type="update",
                    old_values={"description": old_desc},
                    new_values={"description": result_description},
                    related_id=result.id
                )
            # No need to log main entry update unless fields on ExperimentalResults itself change

        else:
            # Creating new entry - Check for existing entry at this timepoint first
            existing_result_at_time = db.query(ExperimentalResults).filter(
                ExperimentalResults.experiment_fk == experiment_id, # Filter by FK
                ExperimentalResults.time_post_reaction == time_post_reaction
            ).first()
            if existing_result_at_time:
                 # Use existing_result_at_time.experiment.experiment_id for user-friendly message if needed
                 st.error(f"An entry already exists for this experiment at time {time_post_reaction:.1f}h. Please edit the existing entry instead of adding a new one.")
                 return False

            # Fetch the parent Experiment object using the database ID
            parent_experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
            if not parent_experiment:
                st.error(f"Parent experiment with DB ID {experiment_id} not found.")
                return False

            # Create the main result entry
            result = ExperimentalResults(
                experiment_id=parent_experiment.experiment_id, # String ID
                experiment=parent_experiment, # Relationship
                experiment_fk=parent_experiment.id, # Foreign Key
                time_post_reaction=time_post_reaction,
                result_type=result_type, # Set the PRIMARY type
                description=result_description # Set the description
            )
            db.add(result)
            # Log creation of the main entry? Optional, depends on desired log granularity.
            log_modification(
                db=db,
                experiment_id=parent_experiment.experiment_id,
                modified_table=ExperimentalResults.__tablename__,
                modification_type="create",
                new_values={
                    'time_post_reaction': time_post_reaction,
                    'result_type': result_type.name,
                    'description': result_description,
                    'experiment_fk': parent_experiment.id
                },
                related_id=None # For new entry, related_id might be result.id after flush if preferred
            ) # Example

            # Flush to get the result.id needed for related tables
            db.flush()
            db.refresh(result)


        # --- Save/Update Scalar Data (Always happens) ---
        scalar_entry = _save_or_update_scalar(db, result, scalar_data)

        # --- Save/Update Primary Data (NMR, GC, etc.) ---
        primary_entry = _save_or_update_primary(db, result, primary_data, result_type)

        # --- Handle File Uploads (No changes needed here) ---
        if uploaded_files_data:
            saved_files_info = []
            for file_data in uploaded_files_data:
                uploaded_file = file_data.get('file')
                description = file_data.get('description', '')
                if uploaded_file:
                    exp_str_id = result.experiment.experiment_id
                    storage_folder = f'result_files/exp_{exp_str_id}/res_{result.id}'
                    file_path = save_uploaded_file(uploaded_file, storage_folder, "")
                    if file_path:
                        result_file_entry = ResultFiles(
                            result_id=result.id,
                            file_path=file_path,
                            file_name=uploaded_file.name,
                            file_type=uploaded_file.type,
                            description=description
                        )
                        db.add(result_file_entry)
                        # TODO: Log file additions?
                    else:
                        st.error(f"Failed to save uploaded file: {uploaded_file.name}")
                        db.rollback()
                        return False

        # --- Commit all changes ---
        db.commit()
        action = "updated" if result_id_to_edit else "saved"
        st.success(f"Results (Type: {result_type.name}) and associated data for time point {time_post_reaction:.1f}h {action} successfully!")
        return True

    except ValueError as ve: # Catch specific errors raised by helpers
         db.rollback()
         # Error already shown by helper function
         print(f"ValueError during save: {ve}") # Log for debugging
         return False
    except Exception as e:
        db.rollback()
        st.error(f"An unexpected error occurred saving results/files for time {time_post_reaction:.1f}h: {str(e)}")
        print(f"Detailed error: {e}") # Use proper logging
        import traceback
        traceback.print_exc() # Print stack trace for debugging
        return False
    finally:
        db.close()

def delete_experimental_results(result_id):
    """
    Delete an experimental result time point entry. Cascade delete handles specific data and files.

    Args:
        result_id (int): The unique identifier (DB ID) of the ExperimentalResults entry.
    """
    db = SessionLocal()
    try:
        # Get the main result entry, eager load related data needed for logging/file deletion
        result_entry = db.query(ExperimentalResults).options(
            selectinload(ExperimentalResults.files),
            selectinload(ExperimentalResults.experiment)  # Correctly load the experiment relationship
        ).filter(ExperimentalResults.id == result_id).first()

        if result_entry is None:
            st.error(f"Result entry with ID {result_id} not found.")
            return

        experiment_str_id = result_entry.experiment.experiment_id if result_entry.experiment else None
        time_point = result_entry.time_post_reaction
        result_type_name = result_entry.result_type.name if result_entry.result_type else "Unknown"

        # --- Delete associated files from storage FIRST ---
        associated_files = result_entry.files
        deleted_file_info = []
        if associated_files:
            for file_record in associated_files:
                deleted = delete_file_if_exists(file_record.file_path)
                deleted_file_info.append({
                    'name': file_record.file_name,
                    'path': file_record.file_path,
                    'deleted': deleted
                })
                if not deleted:
                     st.warning(f"Could not delete file from storage: {file_record.file_path}")

        # Prepare old values for the main log entry
        old_values_log = {
            'result_id': result_entry.id,
            'time_post_reaction': time_point,
            'result_type': result_type_name,
            'experiment_id': experiment_str_id,
            'deleted_files_info': deleted_file_info
        }

        # --- Log the deletion of the main result entry ---
        log_modification(
            db=db,
            experiment_id=experiment_str_id,
            modified_table="experimental_results",
            modification_type="delete",
            old_values=old_values_log,
            related_id=result_id
        )

        # --- Delete the ExperimentalResults record ---
        db.delete(result_entry)

        # --- Commit the transaction ---
        db.commit()

        st.success(f"{result_type_name} result entry for time {time_point:.1f}h deleted successfully!")

    except Exception as e:
        db.rollback()
        st.error(f"Error deleting result entry (ID: {result_id}): {str(e)}")
    finally:
        db.close()

def delete_result_file(file_id):
    """
    Delete an individual result file record and its corresponding file from storage.

    Args:
        file_id (int): The unique identifier of the ResultFiles entry to delete.

    Returns:
        bool: True if deletion was successful, False otherwise.
    """
    db = SessionLocal()
    try:
        # Find the file record, eager load parent result and experiment for logging context
        file_record = db.query(ResultFiles).options(
            selectinload(ResultFiles.result_entry).selectinload(ExperimentalResults.experiment)
        ).filter(ResultFiles.id == file_id).first()

        if file_record is None:
            st.error(f"File record with ID {file_id} not found.")
            return False

        # Store info for logging
        old_values = {
            'file_id': file_record.id,
            'result_id': file_record.result_id,
            'file_path': file_record.file_path,
            'file_name': file_record.file_name,
            'description': file_record.description
        }

        # Get the associated experiment string ID for logging context
        experiment_str_id_for_log = None
        if file_record.result_entry and file_record.result_entry.experiment:
             experiment_str_id_for_log = file_record.result_entry.experiment.experiment_id
        else:
             st.warning(f"Could not determine experiment ID for logging file deletion (File ID: {file_id}, Result ID: {file_record.result_id})")


        # --- Delete the actual file from storage FIRST ---
        file_deleted_from_storage = delete_file_if_exists(file_record.file_path)

        if not file_deleted_from_storage:
            st.warning(f"Could not delete file from storage: {file_record.file_path}. Proceeding to remove database record.")
            old_values['storage_deletion_failed'] = True

        # --- Delete the database record ---
        db.delete(file_record)

        # --- Log the deletion ---
        log_modification(
            db=db,
            experiment_id=experiment_str_id_for_log, # Log against the parent experiment's string ID
            modified_table="result_files", # Indicate which table
            modification_type="delete",
            old_values=old_values, # Log the details of the deleted file record
            related_id=file_record.result_id # Log the parent result ID
        )

        # --- Commit the transaction ---
        db.commit()
        st.success(f"File '{old_values.get('file_name', 'Unknown')}' deleted successfully.")
        return True

    except Exception as e:
        db.rollback()
        st.error(f"Error deleting file record (ID: {file_id}): {str(e)}")
        return False
    finally:
        db.close()

# TODO: Add function `process_uploaded_results_file(file)`
# This function would handle parsing CSV/Excel, validating data,
# and returning structured data ready for `save_results`.
# It could potentially use the ResultHandler classes mentioned above.

# TODO: Add function `calculate_derived_results(experiment_id)`
# This function could be triggered after saving primary results
# to calculate things like yield based on other data points.
# Consider triggering this within save_results after commit, or as a separate process. 