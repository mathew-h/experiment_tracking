import pandas as pd
import re
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from database import Experiment, ExperimentalResults, ICPResults
from io import StringIO

class ICPService:
    """Service for handling ICP elemental analysis data operations."""
    
    @staticmethod
    def parse_csv_file(file_content: bytes) -> pd.DataFrame:
        """
        Parse CSV file starting from row 3 to skip header information.
        
        Args:
            file_content: Raw bytes content of the CSV file
            
        Returns:
            DataFrame with CSV data starting from row 3
        """
        try:
            # Convert bytes to string
            csv_string = file_content.decode('utf-8')
            
            # Read CSV starting from row 3 (skip first 2 rows which are headers)
            df = pd.read_csv(StringIO(csv_string), skiprows=2)
            
            # Clean up any unnamed columns or empty columns
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
            df = df.dropna(how='all')  # Remove completely empty rows
            
            return df
            
        except Exception as e:
            raise ValueError(f"Error parsing CSV file: {str(e)}")
    
    @staticmethod
    def extract_sample_info(label: str) -> Dict[str, Any]:
        """
        Extract experiment ID, time point, and dilution factor from label column.
        
        Expected format: 'Serum_MH_011_Day5_5x' or 'Serum-MH-011_Day5_5x'
        Supports dashes and underscores in experiment IDs.
        
        Args:
            label: Sample label string
            
        Returns:
            Dictionary with experiment_id, time_post_reaction, and dilution_factor
            Returns None if label doesn't match expected pattern (e.g., "Standard 1", "Blank")
        """
        try:
            # Pattern to match: ExpID_(Day|Time)Number_DilutionFactorx
            # More robust approach to handle dashes/underscores in experiment IDs
            # Examples: Serum_MH_011_Day5_5x, Serum-MH-025_Time3_10x, Test_Sample_A_Day1_2x
            
            # Use search from the end to find the last occurrence of the time pattern
            time_pattern = r'_(Day|Time)(\d+(?:\.\d+)?)_(\d+(?:\.\d+)?)x?$'
            time_match = re.search(time_pattern, label, re.IGNORECASE)
            
            if not time_match:
                # Return None for non-matching labels (Standards, Blanks, etc.)
                return None
            
            # Extract the experiment ID by removing the time pattern from the end
            experiment_id = label[:time_match.start()]
            time_unit = time_match.group(1).lower()
            time_value = float(time_match.group(2))
            dilution_factor = float(time_match.group(3))
            
            # Convert time to days if needed
            if time_unit == 'time':
                # Assume 'Time' units are in days (adjust if different)
                time_post_reaction = time_value
            else:  # 'day'
                time_post_reaction = time_value
            
            return {
                'experiment_id': experiment_id,
                'time_post_reaction': time_post_reaction,
                'dilution_factor': dilution_factor
            }
            
        except Exception as e:
            # Return None for any parsing errors instead of raising
            return None
    
    @staticmethod
    def apply_dilution_correction(df: pd.DataFrame, dilution_factor: float) -> pd.DataFrame:
        """
        Apply dilution factor to concentration values to get absolute concentrations.
        For long-format data, this applies to the Concentration column.
        
        Args:
            df: DataFrame with long-format elemental data
            dilution_factor: Dilution factor to apply (e.g., 5.0 for 5x dilution)
            
        Returns:
            DataFrame with corrected concentrations
        """
        df_corrected = df.copy()
        
        if 'Concentration' in df_corrected.columns:
            # Apply dilution correction to Concentration column
            df_corrected['Corrected_Concentration'] = (
                pd.to_numeric(df_corrected['Concentration'], errors='coerce') * dilution_factor
            )
        else:
            raise ValueError("DataFrame must contain 'Concentration' column for dilution correction")
        
        return df_corrected
    
    @staticmethod
    def select_best_lines(df: pd.DataFrame) -> pd.DataFrame:
        """
        Select the row with highest intensity for each element per sample.
        Handles long-format data where each row is one element measurement.
        
        Expected columns: Label, Element Label, Intensity
        
        Args:
            df: DataFrame with long-format elemental data
            
        Returns:
            DataFrame with best line selected for each element per sample
        """
        required_columns = ['Label', 'Element Label', 'Intensity']
        if not all(col in df.columns for col in required_columns):
            raise ValueError(f"DataFrame must contain columns: {required_columns}")
        
        # Convert Intensity to numeric, handling any non-numeric values
        df = df.copy()
        df['Intensity'] = pd.to_numeric(df['Intensity'], errors='coerce')
        
        # Group by Label and Element, select row with maximum intensity
        # This handles multiple wavelengths/lines per element
        best_rows = []
        
        for (label, element), group in df.groupby(['Label', 'Element Label']):
            if len(group) == 1:
                # Only one measurement for this element
                best_rows.append(group.iloc[0])
            else:
                # Multiple lines for this element, select the one with highest intensity
                max_intensity_idx = group['Intensity'].idxmax()
                if pd.notna(max_intensity_idx):  # Check for valid max index
                    best_rows.append(df.loc[max_intensity_idx])
                else:
                    # If all intensities are NaN, take the first row
                    best_rows.append(group.iloc[0])
        
        return pd.DataFrame(best_rows).reset_index(drop=True)
    
    @staticmethod
    def process_icp_dataframe(df: pd.DataFrame) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Process the entire ICP DataFrame from long-format to sample-based data for upload.
        
        Expected DataFrame structure:
        - Label: Sample identifiers (e.g., 'Serum_MH_011_Day5_5x')  
        - Element Label: Element with wavelength (e.g., 'Al 394.401', 'Fe 238.204')
        - Concentration: Raw concentration values
        - Intensity: Measurement values (for quality assessment)
        - Type: Sample type (filter out 'BLK' blanks)
        
        Args:
            df: Raw ICP DataFrame in long format
            
        Returns:
            Tuple of (processed_data_list, error_messages)
        """
        processed_data = []
        errors = []
        
        if df.empty:
            errors.append("DataFrame is empty")
            return processed_data, errors
        
        # Validate required columns
        required_columns = ['Label', 'Element Label', 'Concentration', 'Intensity']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            errors.append(f"Missing required columns: {missing_columns}")
            return processed_data, errors
        
        try:
            # Filter out blank samples (Type = 'BLK' or Label contains 'Blank')
            if 'Type' in df.columns:
                df_samples = df[df['Type'] != 'BLK'].copy()
            else:
                df_samples = df[~df['Label'].str.contains('Blank', case=False, na=False)].copy()
            
            if df_samples.empty:
                errors.append("No non-blank samples found in data")
                return processed_data, errors
            
            # Get unique sample labels
            unique_labels = df_samples['Label'].unique()
            
            for label in unique_labels:
                try:
                    # Extract sample information (experiment_id, time, dilution)
                    sample_info = ICPService.extract_sample_info(label)
                    
                    # Skip rows that don't match expected pattern (Standards, Blanks, etc.)
                    if sample_info is None:
                        errors.append(f"Sample '{label}': Skipped - Label format not recognized (likely Standard/Blank/QC sample)")
                        continue
                    
                    # Get all data for this sample
                    sample_data = df_samples[df_samples['Label'] == label].copy()
                    
                    # Apply dilution correction to this sample's data
                    sample_data_corrected = ICPService.apply_dilution_correction(
                        sample_data, sample_info['dilution_factor']
                    )
                    
                    # Select best lines for each element
                    best_lines = ICPService.select_best_lines(sample_data_corrected)
                    
                    # Pivot from long format to wide format (one row per sample)
                    elemental_data = {}
                    for _, row in best_lines.iterrows():
                        # Extract element symbol from 'Element Label' (e.g., 'Al 394.401' -> 'Al')
                        element_label = str(row['Element Label']).strip()
                        element = element_label.split()[0]  # Get first part before space
                        concentration = row['Corrected_Concentration']
                        
                        if pd.notna(concentration):
                            # Standardize element name for database
                            element_key = ICPService._standardize_element_name(element)
                            elemental_data[element_key] = float(concentration)
                    
                    # Combine sample info with elemental data
                    result_data = {
                        **sample_info,
                        **elemental_data,
                        'raw_label': label
                    }
                    
                    processed_data.append(result_data)
                    
                except Exception as e:
                    errors.append(f"Sample '{label}': Error processing - {str(e)}")
        
        except Exception as e:
            errors.append(f"Error processing DataFrame: {str(e)}")
        
        return processed_data, errors
    
    @staticmethod
    def _standardize_element_name(element_symbol: str) -> str:
        """
        Standardize element symbols to database field names.
        
        Args:
            element_symbol: Element symbol from CSV (e.g., 'Fe', 'Mg', 'Al')
            
        Returns:
            Standardized element name for database (lowercase)
        """
        # Clean element symbol
        clean_symbol = element_symbol.strip().lower()
        
        # Map element symbols to standard lowercase versions
        # Most symbols are already correct, but handle special cases
        symbol_mapping = {
            'al': 'al',   # Aluminum
            'ca': 'ca',   # Calcium  
            'co': 'co',   # Cobalt
            'cr': 'cr',   # Chromium
            'cu': 'cu',   # Copper
            'fe': 'fe',   # Iron
            'k': 'k',     # Potassium
            'mg': 'mg',   # Magnesium
            'mn': 'mn',   # Manganese
            'mo': 'mo',   # Molybdenum
            'na': 'na',   # Sodium
            'ni': 'ni',   # Nickel
            'si': 'si',   # Silicon
            'zn': 'zn',   # Zinc
            'p': 'p',     # Phosphorus
            's': 's',     # Sulfur
            'ti': 'ti',   # Titanium
            'v': 'v',     # Vanadium
        }
        
        # Return mapped symbol or original if not found
        return symbol_mapping.get(clean_symbol, clean_symbol)
    
    @staticmethod
    def create_icp_result(db: Session, experiment_id: str, result_data: Dict[str, Any]) -> Tuple[Optional[ExperimentalResults], bool]:
        """
        Create an experimental result with ICP elemental analysis data.
        Uses unique result tracking improvements to allow multiple data types per time point.
        
        Args:
            db: Database session
            experiment_id: String experiment ID
            result_data: Dictionary containing result data fields and elemental concentrations
            
        Returns:
            Tuple of (ExperimentalResults object, was_update: bool)
            was_update is True if existing ICP data was updated, False if new data was created
            
        Raises:
            ValueError: If experiment not found
        """
        # Find experiment with normalization
        experiment = ICPService._find_experiment(db, experiment_id)
        if not experiment:
            raise ValueError(f"Experiment with ID '{experiment_id}' not found.")
        
        # Find or create ExperimentalResults using unique result tracking improvements
        experimental_result = ICPService._find_or_create_experimental_result(
            db=db,
            experiment=experiment,
            time_post_reaction=result_data['time_post_reaction'],
            description=f"ICP Analysis - {result_data.get('raw_label', 'Unknown')}"
        )
        
        # Separate fixed columns from all elemental data
        fixed_elements = ['fe', 'si', 'ni', 'cu', 'mo', 'zn', 'mn', 'cr', 'co', 'mg', 'al']
        fixed_column_data = {}
        all_elements_data = {}
        
        # Extract fixed columns and prepare all elements JSON
        for key, value in result_data.items():
            if key in fixed_elements and value is not None:
                fixed_column_data[key] = value
                all_elements_data[key] = value  # Also store in JSON for completeness
            elif key not in ['experiment_id', 'time_post_reaction', 'dilution_factor', 'raw_label'] and value is not None:
                all_elements_data[key] = value  # Store additional elements in JSON only
        
        # Check if ICPResults already exists for this ExperimentalResults
        if experimental_result.icp_data:
            # Update existing ICP data instead of rejecting
            existing_icp = experimental_result.icp_data
            
            # Update fixed columns
            for element in fixed_elements:
                setattr(existing_icp, element, fixed_column_data.get(element))
            
            # Update JSON and metadata
            existing_icp.all_elements = all_elements_data if all_elements_data else None
            existing_icp.dilution_factor = result_data.get('dilution_factor')
            existing_icp.raw_label = result_data.get('raw_label')
            
            db.flush()  # Flush to ensure update is applied
            return experimental_result, True  # True indicates this was an update
        
        # Create ICP data with elemental concentrations
        icp_data = ICPResults(
            result_id=experimental_result.id,  # Link to ExperimentalResults
            # Fixed columns for Power BI efficiency
            fe=fixed_column_data.get('fe'),
            si=fixed_column_data.get('si'),
            ni=fixed_column_data.get('ni'),
            cu=fixed_column_data.get('cu'),
            mo=fixed_column_data.get('mo'),
            zn=fixed_column_data.get('zn'),
            mn=fixed_column_data.get('mn'),
            cr=fixed_column_data.get('cr'),
            co=fixed_column_data.get('co'),
            mg=fixed_column_data.get('mg'),
            al=fixed_column_data.get('al'),
            # JSON storage for all elements (including fixed ones)
            all_elements=all_elements_data if all_elements_data else None,
            # ICP metadata
            dilution_factor=result_data.get('dilution_factor'),
            raw_label=result_data.get('raw_label'),
            # Relationship
            result_entry=experimental_result
        )
        
        # Add to session (commit handled by caller)
        db.add(experimental_result)  # May be existing or new
        db.flush()  # Flush to get IDs assigned
        
        return experimental_result, False  # False indicates this was a new creation
    
    @staticmethod
    def bulk_create_icp_results(db: Session, processed_data: List[Dict[str, Any]]) -> Tuple[List[ExperimentalResults], List[str]]:
        """
        Bulk create ICP results with validation and error collection.
        
        Args:
            db: Database session
            processed_data: List of processed ICP data dictionaries
            
        Returns:
            Tuple of (successful_results, error_messages)
        """
        results_to_add = []
        errors = []
        
        for idx, data in enumerate(processed_data):
            try:
                experiment_id = data.get('experiment_id')
                time_post_reaction = data.get('time_post_reaction')
                
                if not experiment_id:
                    errors.append(f"Sample {idx + 1}: Missing experiment_id.")
                    continue
                
                if time_post_reaction is None:
                    errors.append(f"Sample {idx + 1}: Missing time_post_reaction.")
                    continue
                
                # Create or update the ICP result
                result, was_update = ICPService.create_icp_result(
                    db=db,
                    experiment_id=experiment_id,
                    result_data=data
                )
                
                if result:
                    results_to_add.append(result)
                    
                    # Add informational message for overwrites
                    if was_update:
                        errors.append(f"Sample {idx + 1}: Updated existing ICP data for experiment '{experiment_id}' at time {time_post_reaction} days")
                    
            except ValueError as e:
                errors.append(f"Sample {idx + 1}: {str(e)}")
            except Exception as e:
                errors.append(f"Sample {idx + 1}: Unexpected error - {str(e)}")
        
        return results_to_add, errors
    
    @staticmethod
    def get_icp_results_for_experiment(db: Session, experiment_id: str) -> List[ICPResults]:
        """
        Retrieve all ICP results for an experiment.
        
        Args:
            db: Database session
            experiment_id: String experiment ID
            
        Returns:
            List of ICPResults objects
        """
        return (db.query(ICPResults)
                .join(ExperimentalResults)
                .filter(ExperimentalResults.experiment_id == experiment_id)
                .all())
    
    @staticmethod
    def update_icp_result(db: Session, result_id: int, update_data: Dict[str, Any]) -> Optional[ICPResults]:
        """
        Update an existing ICP result with new elemental data.
        
        Args:
            db: Database session
            result_id: ID of the ExperimentalResults entry
            update_data: Dictionary of fields to update
            
        Returns:
            Updated ICPResults object or None if not found
        """
        icp_result = db.query(ICPResults).filter(ICPResults.result_id == result_id).first()
        
        if not icp_result:
            raise ValueError(f"ICPResult with result_id {result_id} not found.")
        
        # Update fixed columns
        fixed_elements = ['fe', 'si', 'ni', 'cu', 'mo', 'zn', 'mn', 'cr', 'co', 'mg', 'al']
        for element in fixed_elements:
            if element in update_data:
                setattr(icp_result, element, update_data[element])
        
        # Update metadata fields
        metadata_fields = ['dilution_factor', 'analysis_date', 'instrument_used', 'detection_limits', 'raw_label']
        for field in metadata_fields:
            if field in update_data:
                setattr(icp_result, field, update_data[field])
        
        # Update JSON data if provided
        if 'all_elements' in update_data:
            icp_result.all_elements = update_data['all_elements']
        
        db.flush()
        return icp_result
    
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
        ).first()
        
        return experiment
    
    @staticmethod
    def _find_or_create_experimental_result(
        db: Session, 
        experiment: Experiment, 
        time_post_reaction: float, 
        description: str = None
    ) -> ExperimentalResults:
        """
        Find existing ExperimentalResults or create new one.
        Core logic for unique result tracking improvements.
        
        Args:
            db: Database session
            experiment: Experiment object
            time_post_reaction: Time point in days
            description: Optional description
            
        Returns:
            ExperimentalResults object (existing or new)
        """
        existing_result = db.query(ExperimentalResults).filter_by(
            experiment_fk=experiment.id,
            time_post_reaction=time_post_reaction
        ).first()
        
        if existing_result:
            return existing_result
        else:
            # Create new ExperimentalResults
            new_result = ExperimentalResults(
                experiment_id=experiment.experiment_id,
                experiment_fk=experiment.id,
                time_post_reaction=time_post_reaction,
                description=description or f"Analysis results for Day {time_post_reaction}"
            )
            db.add(new_result)
            db.flush()  # Get ID assigned
            return new_result
    
    @staticmethod
    def validate_icp_data(processed_data: List[Dict[str, Any]]) -> List[str]:
        """
        Validate processed ICP data for common issues.
        
        Args:
            processed_data: List of processed data dictionaries
            
        Returns:
            List of validation error messages
        """
        errors = []
        
        if not processed_data:
            errors.append("No data to validate")
            return errors
        
        for idx, data in enumerate(processed_data):
            sample_id = f"Sample {idx + 1}"
            
            # Check required fields
            if not data.get('experiment_id'):
                errors.append(f"{sample_id}: Missing experiment_id")
            
            if data.get('time_post_reaction') is None:
                errors.append(f"{sample_id}: Missing time_post_reaction")
            
            if not data.get('dilution_factor'):
                errors.append(f"{sample_id}: Missing dilution_factor")
            
            # Check for elemental data
            elemental_keys = [k for k in data.keys() if k not in ['experiment_id', 'time_post_reaction', 'dilution_factor', 'raw_label']]
            if not elemental_keys:
                errors.append(f"{sample_id}: No elemental concentration data found")
        
        return errors
    
    @staticmethod
    def parse_and_process_icp_file(file_content: bytes) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Complete workflow to parse and process ICP CSV file.
        
        This function orchestrates the entire ICP data processing pipeline:
        1. Parse CSV file (skip header rows 0-2)
        2. Filter out blank samples  
        3. Extract experiment info from sample labels
        4. Apply dilution corrections
        5. Select best lines for each element
        6. Convert from long to wide format
        7. Validate processed data
        
        Args:
            file_content: Raw bytes content of the CSV file
            
        Returns:
            Tuple of (processed_data_list, error_messages)
        """
        try:
            # Step 1: Parse CSV file (skip header rows)
            df = ICPService.parse_csv_file(file_content)
            
            if df.empty:
                return [], ["Parsed CSV file is empty"]
            
            # Step 2: Process the DataFrame
            processed_data, processing_errors = ICPService.process_icp_dataframe(df)
            
            # Step 3: Validate the processed data
            validation_errors = ICPService.validate_icp_data(processed_data)
            
            # Combine all errors
            all_errors = processing_errors + validation_errors
            
            return processed_data, all_errors
            
        except Exception as e:
            return [], [f"Error in ICP file processing workflow: {str(e)}"]
