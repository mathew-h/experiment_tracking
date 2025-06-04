import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# Add the project root to the Python path to allow importing models
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')) # Adjusted path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.database import DATABASE_URL, Base # Assuming your DATABASE_URL and Base are here
from database.models import Experiment # Assuming your Experiment model is here

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
        # COMPLETED and CANCELLED remain as is, so no explicit mapping needed here
    }

    updated_count = 0
    failed_count = 0

    try:
        print("Starting experiment status data migration...")
        experiments_to_update = session.query(Experiment).filter(
            Experiment.status.in_(list(status_mapping.keys()))
        ).all()

        if not experiments_to_update:
            print("No experiments found with statuses requiring update.")
            return

        print(f"Found {len(experiments_to_update)} experiments to update.")

        for exp in experiments_to_update:
            old_status = str(exp.status) # Get the string value of the enum
            if old_status in status_mapping:
                new_status = status_mapping[old_status]
                print(f"Updating Experiment ID {exp.experiment_id} (DB ID: {exp.id}): status from '{old_status}' to '{new_status}'")
                exp.status = new_status # SQLAlchemy handles enum conversion
                updated_count += 1
            else:
                # This case should ideally not be hit if the query is correct
                print(f"Skipping Experiment ID {exp.experiment_id} (DB ID: {exp.id}): status '{old_status}' not in mapping.")


        session.commit()
        print(f"Successfully updated statuses for {updated_count} experiments.")

    except SQLAlchemyError as e:
        session.rollback()
        print(f"Error during data migration: {e}")
        print("Transaction rolled back.")
        failed_count = len(experiments_to_update) # Approximate, as some might have succeeded before error
    except Exception as e:
        session.rollback()
        print(f"An unexpected error occurred: {e}")
        print("Transaction rolled back.")
        failed_count = len(experiments_to_update)
    finally:
        session.close()
        print("Data migration finished.")
        if failed_count > 0:
            print(f"Warning: {failed_count} experiments might not have been updated due to errors.")

if __name__ == "__main__":
    # This allows running the script directly.
    # Ensure your DATABASE_URL is correctly configured in your environment or database.py
    print("Attempting to run data migration for experiment statuses...")
    run_data_migration()
    print("Script execution complete.") 