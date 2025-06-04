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

        # Step 1: Fetch IDs and current statuses using a raw SQL IN clause
        # This avoids Python-side enum validation on the filter values.
        # Get the actual column name for 'status' from the Experiment model
        status_column_name = Experiment.status.property.columns[0].name

        # Create a placeholder string for the IN clause, e.g., "('PLANNED', 'IN_PROGRESS', 'FAILED')"
        in_clause_values = ", ".join([f"'{s}'" for s in status_mapping.keys()])
        raw_where_clause = f"{status_column_name} IN ({in_clause_values})"

        # Select the id and the status column (referred to by its string name)
        # from the actual table reflected by the Experiment model.
        stmt = select(
            Experiment.__table__.c.id, # Select id column directly from table metadata
            Experiment.__table__.c[status_column_name].label("current_status") # Select status column by name
        ).select_from(Experiment.__table__).where(
            text(raw_where_clause) # Use the raw SQL WHERE clause
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
            old_status_str = exp_info["current_status"]

            if old_status_str in status_mapping:
                new_status_str = status_mapping[old_status_str]
                try:
                    print(f"Updating Experiment DB ID {exp_id}: status from '{old_status_str}' to '{new_status_str}'")
                    update_stmt = (
                        update(Experiment)
                        .where(Experiment.id == exp_id)
                        .values(status=new_status_str) # new_status_str is valid in current Python enum
                    )
                    session.execute(update_stmt)
                    updated_count += 1
                except Exception as e_update:
                    print(f"Error updating experiment ID {exp_id}: {e_update}")
                    failed_count +=1 
            else:
                print(f"Skipping Experiment DB ID {exp_id}: status '{old_status_str}' not in explicit mapping.")

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
        if experiments_needing_update_info:
             failed_count = len(experiments_needing_update_info) - updated_count
    except Exception as e_general:
        session.rollback()
        print(f"An unexpected error occurred: {e_general}")
        print("Transaction rolled back.")
        if experiments_needing_update_info:
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