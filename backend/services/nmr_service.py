from typing import Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from database.models import NMRResults, Experiment, ExperimentalConditions, ScalarResults, ExperimentalResults, ResultType
from database.database import SessionLocal

class NMRService:
    @staticmethod
    def create_nmr_result(db: Session, experiment_id: str, nmr_data: Dict[str, Any]) -> Optional[NMRResults]:
        """
        Create a new NMR result entry with calculated values.
        NOTE: Does NOT handle associated ScalarResults yield updates anymore.
        This service might become less relevant as save_results handles more.
        """
        # Find parent ExperimentalResults or create if needed
        # This assumes time_post_reaction is part of nmr_data
        time_post_reaction = nmr_data.get('time_post_reaction')
        if time_post_reaction is None:
             # Handle error: time_post_reaction is required
             print("Error: time_post_reaction missing from nmr_data") # Replace with proper logging/exception
             return None 

        # Get the experiment to get its ID for the foreign key
        experiment = db.query(Experiment).filter(Experiment.experiment_id == experiment_id).first()
        if not experiment:
            print(f"Error: Experiment with ID {experiment_id} not found.") # Replace with proper logging/exception
            return None

        # Check if an ExperimentalResults entry already exists for this NMR point
        result_entry = db.query(ExperimentalResults).filter(
            ExperimentalResults.experiment_id == experiment_id,
            ExperimentalResults.time_post_reaction == time_post_reaction,
            ExperimentalResults.result_type == ResultType.NMR
        ).first()

        if not result_entry:
            # Create parent ExperimentalResults entry if it doesn't exist
            result_entry = ExperimentalResults(
                experiment_id=experiment_id,
                experiment_fk=experiment.id,  # Set the foreign key to the experiment's ID
                time_post_reaction=time_post_reaction,
                result_type=ResultType.NMR,
                description=nmr_data.get('description'), # Optional description
                experiment=experiment  # Set the relationship directly
            )
            db.add(result_entry)
            db.flush() # Flush to get the result_entry.id

        # Create new NMR result linked to the ExperimentalResults entry
        nmr_result = NMRResults(
            result_id=result_entry.id, # Link to the parent entry
            is_concentration_mm=nmr_data.get('is_concentration_mm', 0.0263),
            is_protons=nmr_data.get('is_protons', 2),
            sampled_rxn_volume_ul=nmr_data.get('sampled_rxn_volume_ul', 476.0),
            nmr_total_volume_ul=nmr_data.get('nmr_total_volume_ul', 647.0),
            nh4_peak_area_1=nmr_data.get('nh4_peak_area_1'),
            nh4_peak_area_2=nmr_data.get('nh4_peak_area_2'),
            nh4_peak_area_3=nmr_data.get('nh4_peak_area_3'),
            result_entry=result_entry  # Set the relationship directly
        )
        
        # Calculate NMR values (including ammonia_mass_g)
        nmr_result.calculate_values()
        
        # Add NMR result to database
        db.add(nmr_result)
        
        db.commit() # Commit changes (ExperimentalResults, NMRResults)
        db.refresh(result_entry) # Refresh the parent entry might be useful
        db.refresh(nmr_result) # Refresh the NMR entry
        
        return nmr_result

    @staticmethod
    def update_nmr_result(db: Session, result_id: int, nmr_data: Dict[str, Any]) -> Optional[NMRResults]:
        """
        Update an existing NMR result and recalculate values.
        NOTE: Does NOT handle associated ScalarResults yield updates anymore.
        This service might become less relevant as save_results handles more.
        """
        # Find the NMRResult by its specific result_id (which links to ExperimentalResults.id)
        nmr_result = db.query(NMRResults).filter(NMRResults.result_id == result_id).first()
        
        if not nmr_result:
            print(f"Error: NMRResult with result_id {result_id} not found.") # Use logger
            return None

        # Get parent ExperimentalResults to access experiment_id and time_post_reaction
        result_entry = nmr_result.result_entry 
        if not result_entry:
             print(f"Error: Could not find parent ExperimentalResults for NMRResult {result_id}") # Use logger
             return None

        experiment_id = result_entry.experiment_id
        time_post_reaction = result_entry.time_post_reaction
            
        # Update NMR fields from nmr_data
        for field, value in nmr_data.items():
            if hasattr(nmr_result, field):
                setattr(nmr_result, field, value)
        
        # Recalculate NMR values (including ammonia_mass_g)
        nmr_result.calculate_values()
        
        db.commit() # Commit changes to NMRResults
        db.refresh(nmr_result)
        
        return nmr_result

    @staticmethod
    def get_nmr_result(db: Session, result_id: int) -> Optional[NMRResults]:
        """
        Retrieve an NMR result by its ID (which is the ForeignKey to ExperimentalResults.id).
        """
        # Correctly query by NMRResults.result_id which is the FK to ExperimentalResults.id
        return db.query(NMRResults).filter(NMRResults.result_id == result_id).first()

    @staticmethod
    def get_nmr_results_for_experiment(db: Session, experiment_id: str) -> list[NMRResults]:
        """
        Retrieve all NMR results for an experiment.
        """
        # Join with ExperimentalResults to filter by experiment_id
        return db.query(NMRResults).join(ExperimentalResults).filter(ExperimentalResults.experiment_id == experiment_id).all() 