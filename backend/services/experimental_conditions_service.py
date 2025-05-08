from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from database.models import ExperimentalConditions, Experiment

class ExperimentalConditionsService:
    
    @staticmethod
    def create_experimental_conditions(db: Session, experiment_id: str, conditions_data: Dict[str, Any]) -> Optional[ExperimentalConditions]:
        """
        Creates a new ExperimentalConditions record for a given experiment.

        Args:
            db: The database session.
            experiment_id: The string ID of the parent experiment.
            conditions_data: A dictionary containing the condition values.

        Returns:
            The created ExperimentalConditions object, or None if the experiment doesn't exist.
        """
        # Optional: Validate if the parent experiment exists
        experiment = db.query(Experiment).filter(Experiment.experiment_id == experiment_id).first()
        if not experiment:
            # Handle error: Experiment not found (log or raise exception)
            print(f"Error: Experiment with ID {experiment_id} not found.") 
            return None

        # Create the ExperimentalConditions instance
        # Ensure the foreign key 'experiment_id' (referencing Experiment.id) is correctly set
        # If your model expects the parent object's PK id:
        # conditions_data['experiment_id'] = experiment.id 
        # If your model expects the string experiment_id directly (less common for FKs but check your model):
        # conditions_data['experiment_id'] = experiment_id 
        # Let's assume the FK links to Experiment.id based on standard practice
        conditions_data['experiment_id'] = experiment.experiment_id # Correct based on model definition

        conditions = ExperimentalConditions(**conditions_data)
        
        # *** Call the method to calculate derived fields ***
        conditions.calculate_derived_conditions()
        
        # Add to the session (commit will happen in the calling context, e.g., Experiment service)
        db.add(conditions)
        db.flush() # Flush to assign ID if needed immediately
        db.refresh(conditions) # Refresh to get any DB-generated values
        
        return conditions

    # You might also add update/get methods here later
    # @staticmethod
    # def update_experimental_conditions(db: Session, conditions_id: int, update_data: Dict[str, Any]) -> Optional[ExperimentalConditions]:
    #     ...

    # @staticmethod
    # def get_experimental_conditions(db: Session, experiment_id: str) -> Optional[ExperimentalConditions]:
    #     ...
