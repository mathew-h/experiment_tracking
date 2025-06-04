import sys
import os
from sqlalchemy import create_engine, text, select, update, column
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# Add the project root to the Python path to allow importing models
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')) # Adjusted path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.database import DATABASE_URL
from database.models import Experiment # Still needed for table metadata for raw query

def run_data_migration():
    """
    Updates existing experiment statuses according to the defined mapping:
    PLANNED -> ONGOING
    IN_PROGRESS -> ONGOING
    FAILED -> CANCELLED
    """
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    status_mapping = {
        "PLANNED": "ONGOING",
        "IN_PROGRESS": "ONGOING",
        "FAILED": "CANCELLED"
    }

    updated_count = 0
    failed_count = 0
    # Initialize experiments_to_update to prevent UnboundLocalError
    experiments_needing_update_info = []

    try:
        print("Starting experiment status data migration...")

        # Step 1: Fetch IDs and current statuses (as strings) for experiments needing update
        # This avoids premature full object loading with enum conflicts.
        stmt = select(Experiment.id, Experiment.status.label("current_status")).where(
            Experiment.status.in_(list(status_mapping.keys()))
        )
        result = session.execute(stmt).fetchall()
        
        experiments_needing_update_info = [
            {"id": row.id, "current_status": str(row.current_status)} for row in result
        ]

        if not experiments_needing_update_info:
            print("No experiments found with statuses requiring update.")
            session.close()
            return

        print(f"Found {len(experiments_needing_update_info)} experiments to potentially update.")

        # Step 2: Iterate and update each experiment
        for exp_info in experiments_needing_update_info:
            exp_id = exp_info["id"]
            old_status_str = exp_info["current_status"] # This is already a string

            if old_status_str in status_mapping:
                new_status_str = status_mapping[old_status_str]
                try:
                    print(f"Updating Experiment DB ID {exp_id}: status from '{old_status_str}' to '{new_status_str}'")
                    # Use SQLAlchemy's update() for targeted update
                    # The new_status_str should be a valid member of the *current* Python enum
                    # and the database ENUM type (after Alembic migration)
                    update_stmt = (
                        update(Experiment)
                        .where(Experiment.id == exp_id)
                        .values(status=new_status_str) # Rely on SQLAlchemy to handle enum if Experiment.status is still an enum
                                                      # Or directly use the string if the column type supports it
                    )
                    session.execute(update_stmt)
                    updated_count += 1
                except Exception as e_update:
                    print(f"Error updating experiment ID {exp_id}: {e_update}")
                    failed_count +=1 # Increment failed_count for this specific experiment
                    # Optionally, decide if you want to rollback immediately or continue with others
            else:
                print(f"Skipping Experiment DB ID {exp_id}: status '{old_status_str}' not in explicit mapping (should not happen with current logic).")


        if failed_count > 0:
             print(f"Warning: {failed_count} experiment(s) failed to update. Rolling back transaction.")
             session.rollback()
        else:
            session.commit()
            print(f"Successfully processed {updated_count} experiments for status update.")
            if updated_count > 0 and failed_count == 0:
                 print("All changes committed.")


    except SQLAlchemyError as e_outer:
        session.rollback()
        print(f"SQLAlchemyError during data migration: {e_outer}")
        print("Transaction rolled back.")
        if experiments_needing_update_info: # If we got this far
             failed_count = len(experiments_needing_update_info) - updated_count
    except Exception as e_general:
        session.rollback()
        print(f"An unexpected error occurred: {e_general}")
        print("Transaction rolled back.")
        if experiments_needing_update_info: # If we got this far
            failed_count = len(experiments_needing_update_info) - updated_count
    finally:
        session.close()
        print("Data migration finished.")
        if failed_count > 0:
            print(f"Warning: {failed_count} experiment(s) may not have been updated or processing failed.")

if __name__ == "__main__":
    print("Attempting to run data migration for experiment statuses...")
    run_data_migration()
    print("Script execution complete.") 