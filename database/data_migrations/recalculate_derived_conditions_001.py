import sys
import os
from sqlalchemy.orm import Session

# Add the project root to the Python path to allow for module imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.database import SessionLocal
from database.models import ExperimentalConditions

def run_migration():
    """
    Recalculates derived conditions for all existing experiments.
    
    This script iterates through every 'ExperimentalConditions' entry in the database,
    calls the 'calculate_derived_conditions' method on it to apply the latest
    calculation logic for fields like catalyst_percentage and catalyst_ppm,
    and commits the updated values back to the database.
    """
    db: Session = SessionLocal()
    try:
        print("Starting data migration: Recalculating derived conditions for all experiments...")
        
        conditions_to_update = db.query(ExperimentalConditions).all()
        
        if not conditions_to_update:
            print("No experimental conditions found to update.")
            return

        updated_count = 0
        for conditions in conditions_to_update:
            # The updated calculation logic is in the model's method.
            # Calling it will recalculate and set the values on the instance.
            conditions.calculate_derived_conditions()
            updated_count += 1

        print(f"Recalculated conditions for {updated_count} experiments. Committing changes to the database...")
        db.commit()
        print("Data migration completed successfully.")
        
    except Exception as e:
        print(f"An error occurred during the migration: {e}")
        print("Rolling back changes...")
        db.rollback()
    finally:
        print("Closing database session.")
        db.close()

if __name__ == "__main__":
    run_migration() 