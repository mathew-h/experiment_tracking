from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from database import Experiment, ExperimentalResults, ScalarResults

class ScalarResultsService:
    """Service for handling scalar results (solution chemistry) operations."""
    
    @staticmethod
    def create_scalar_result(db: Session, experiment_id: str, result_data: Dict[str, Any]) -> Optional[ExperimentalResults]:
        """
        Create or upsert an experimental result with scalar chemistry data.
        If an ExperimentalResults entry already exists for the experiment and time point,
        this method will update (merge) the existing ScalarResults record instead of erroring.
        
        Args:
            db: Database session
            experiment_id: String experiment ID
            result_data: Dictionary containing result data fields
            
        Returns:
            ExperimentalResults object (existing or new) with scalar data attached
            
        Raises:
            ValueError: If experiment not found or scalar data already exists for this time point
        """
        # Find experiment with normalization
        experiment = ScalarResultsService._find_experiment(db, experiment_id)
        if not experiment:
            raise ValueError(f"Experiment with ID '{experiment_id}' not found.")
        
        # Find or create ExperimentalResults using unique result tracking improvements
        experimental_result = ScalarResultsService._find_or_create_experimental_result(
            db=db,
            experiment=experiment,
            time_post_reaction=result_data['time_post_reaction'],
            description=result_data.get('description')
        )
        
        # Upsert ScalarResults: update if exists; otherwise create new
        if experimental_result.scalar_data:
            scalar_data = experimental_result.scalar_data
            # Update only provided fields (leave others untouched)
            updatable_fields = [
                'ferrous_iron_yield', 'solution_ammonium_concentration', 'ammonium_quant_method',
                'h2_concentration', 'h2_concentration_unit', 'gas_sampling_volume_ml', 'gas_sampling_pressure',
                'final_ph', 'final_nitrate_concentration', 'final_dissolved_oxygen', 'co2_partial_pressure',
                'final_conductivity', 'final_alkalinity', 'sampling_volume'
            ]
            for field in updatable_fields:
                if field in result_data:
                    setattr(scalar_data, field, result_data.get(field))
                # If a field is omitted in the upload row, we leave existing DB value unchanged (no deletion)
        else:
            # Create scalar data with chemistry measurements
            scalar_data = ScalarResults(
                result_id=experimental_result.id,  # Link to ExperimentalResults
                ferrous_iron_yield=result_data.get('ferrous_iron_yield'),
                solution_ammonium_concentration=result_data.get('solution_ammonium_concentration'),
                ammonium_quant_method=result_data.get('ammonium_quant_method'),
                # Hydrogen fields from bulk upload (optional)
                h2_concentration=result_data.get('h2_concentration'),
                h2_concentration_unit=result_data.get('h2_concentration_unit'),
                gas_sampling_volume_ml=result_data.get('gas_sampling_volume_ml'),
                gas_sampling_pressure=result_data.get('gas_sampling_pressure'),
                final_ph=result_data.get('final_ph'),
                final_nitrate_concentration=result_data.get('final_nitrate_concentration'),
                final_dissolved_oxygen=result_data.get('final_dissolved_oxygen'),
                co2_partial_pressure=result_data.get('co2_partial_pressure'),
                final_conductivity=result_data.get('final_conductivity'),
                final_alkalinity=result_data.get('final_alkalinity'),
                sampling_volume=result_data.get('sampling_volume'),
                result_entry=experimental_result
            )
            db.add(scalar_data)

        # Calculate derived values (yields, conversions, etc.)
        scalar_data.calculate_yields()

        # Touch parent entry and flush IDs if needed
        db.add(experimental_result)
        db.flush()

        return experimental_result
    
    @staticmethod
    def bulk_create_scalar_results(db: Session, results_data: List[Dict[str, Any]]) -> Tuple[List[ExperimentalResults], List[str]]:
        """
        Bulk create scalar results with validation and error collection.
        
        Args:
            db: Database session
            results_data: List of dictionaries containing result data
            
        Returns:
            Tuple of (successful_results, error_messages)
        """
        results_to_add = []
        errors = []
        
        for index, row_data in enumerate(results_data):
            try:
                exp_id_raw = row_data.get('experiment_id')
                if not exp_id_raw:
                    errors.append(f"Row {index + 2}: Missing experiment_id.")
                    continue
                
                # time_post_reaction is now optional - no validation needed
                    
                if not row_data.get('description'):
                    errors.append(f"Row {index + 2}: Missing description.")
                    continue
                
                # Create the result
                new_result = ScalarResultsService.create_scalar_result(
                    db=db,
                    experiment_id=exp_id_raw,
                    result_data=row_data
                )
                
                if new_result:
                    results_to_add.append(new_result)
                    
            except ValueError as e:
                errors.append(f"Row {index + 2}: {str(e)}")
            except Exception as e:
                errors.append(f"Row {index + 2}: Unexpected error - {str(e)}")
        
        return results_to_add, errors
    
    @staticmethod
    def _find_experiment(db: Session, experiment_id: str) -> Optional[Experiment]:
        """
        Find experiment by ID with normalization (case insensitive, ignore hyphens/underscores).
        
        Args:
            db: Database session
            experiment_id: String experiment ID to search for
            
        Returns:
            Experiment object or None if not found
        """
        # Normalize experiment_id: lower case and remove hyphens and underscores
        exp_id_normalized = experiment_id.lower().replace('-', '').replace('_', '')
        
        # Query by normalized experiment_id
        experiment = db.query(Experiment).filter(
            func.lower(func.replace(func.replace(Experiment.experiment_id, '-', ''), '_', '')) == exp_id_normalized
        ).options(joinedload(Experiment.conditions)).first()
        
        return experiment
    
    @staticmethod
    def _find_or_create_experimental_result(
        db: Session, 
        experiment: Experiment, 
        time_post_reaction: float = None, 
        description: str = None
    ) -> ExperimentalResults:
        """
        Create new ExperimentalResults entry.
        With the removal of unique constraints, we always create new entries.
        
        Args:
            db: Database session
            experiment: Experiment object
            time_post_reaction: Time point in days (optional)
            description: Optional description
            
        Returns:
            ExperimentalResults object (new)
        """
        # Create new ExperimentalResults - no unique constraint means we can always create new
        description_text = description
        if not description_text:
            if time_post_reaction is not None:
                description_text = f"Analysis results for Day {time_post_reaction}"
            else:
                description_text = "Analysis results"
        
        new_result = ExperimentalResults(
            experiment_fk=experiment.id,
            time_post_reaction=time_post_reaction,
            description=description_text
        )
        db.add(new_result)
        db.flush()  # Get ID assigned
        return new_result
    
    @staticmethod
    def get_scalar_results_for_experiment(db: Session, experiment_id: str) -> List[ScalarResults]:
        """
        Retrieve all scalar results for an experiment.
        
        Args:
            db: Database session
            experiment_id: String experiment ID
            
        Returns:
            List of ScalarResults objects
        """
        return (db.query(ScalarResults)
                .join(ExperimentalResults)
                .filter(ExperimentalResults.experiment_id == experiment_id)
                .all())
    
    @staticmethod
    def update_scalar_result(db: Session, result_id: int, update_data: Dict[str, Any]) -> Optional[ScalarResults]:
        """
        Update an existing scalar result and recalculate derived values.
        
        Args:
            db: Database session
            result_id: ID of the ExperimentalResults entry
            update_data: Dictionary of fields to update
            
        Returns:
            Updated ScalarResults object or None if not found
        """
        scalar_result = db.query(ScalarResults).filter(ScalarResults.result_id == result_id).first()
        
        if not scalar_result:
            raise ValueError(f"ScalarResult with result_id {result_id} not found.")
        
        # Update fields from update_data
        for field, value in update_data.items():
            if hasattr(scalar_result, field):
                setattr(scalar_result, field, value)
        
        # Recalculate derived values
        scalar_result.calculate_yields()
        
        db.flush()
        return scalar_result
    
    @staticmethod
    def validate_required_fields(data: Dict[str, Any], required_fields: set) -> List[str]:
        """
        Validate that required fields are present in data.
        
        Args:
            data: Dictionary to validate
            required_fields: Set of required field names
            
        Returns:
            List of error messages for missing fields
        """
        errors = []
        missing_fields = required_fields - set(data.keys())
        
        if missing_fields:
            errors.append(f"Missing required fields: {', '.join(missing_fields)}")
        
        return errors
