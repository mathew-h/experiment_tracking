import datetime
import streamlit as st
import os
import json
from database.database import SessionLocal
from database.models import (
    Experiment,
    ExperimentStatus,
    ExperimentalResults,
    ExperimentalConditions,
    ModificationsLog,
    ExperimentNotes,
    ExternalAnalysis
)

def edit_experiment(experiment):
    """Edit an existing experiment."""
    with st.form(key="edit_experiment_form"):
        st.markdown("### Basic Information")
        col1, col2 = st.columns(2)
        
        with col1:
            sample_id = st.text_input("Rock Sample ID", value=experiment['sample_id'])
            researcher = st.text_input("Researcher Name", value=experiment['researcher'])
        
        with col2:
            status = st.selectbox(
                "Experiment Status",
                options=['PLANNED', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED'],
                index=['PLANNED', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED'].index(experiment['status'])
            )
            exp_date = st.date_input(
                "Experiment Date", 
                value=experiment['date'] if isinstance(experiment['date'], datetime.datetime) else datetime.datetime.now()
            )
        
        st.markdown("### Experimental Conditions")
        col3, col4 = st.columns(2)
        
        conditions = experiment.get('conditions', {})
        
        with col3:
            st.markdown("#### Required Parameters")
            
            experiment_type = st.selectbox(
                "Experiment Type",
                options=['Serum', 'Autoclave', 'HPHT', 'Core Flood'],
                index=['Serum', 'Autoclave', 'HPHT', 'Core Flood'].index(conditions.get('experiment_type', 'Serum')) if conditions.get('experiment_type') in ['Serum', 'Autoclave', 'HPHT', 'Core Flood'] else 0
            )
            
            # Fix particle_size input handling
            particle_size = st.number_input(
                "Particle Size (μm)",
                min_value=0.0,
                value=float(conditions.get('particle_size', 0.0)),
                step=0.1,
                format="%.1f",
                help="Enter the particle size in micrometers"
            )
            
            initial_ph = st.number_input(
                "Initial pH",
                min_value=0.0,
                max_value=14.0,
                value=float(conditions.get('initial_ph', 7.0) or 7.0),
                step=0.1,
                format="%.1f"
            )
            
            catalyst = st.text_input(
                "Catalyst",
                value=conditions.get('catalyst', '')
            )
            
            catalyst_mass = st.number_input(
                "Catalyst Mass (g)",
                min_value=0.0,
                value=float(conditions.get('catalyst_mass', 0.0) or 0.0),
                step=0.000001,  # 6 significant figures
                format="%.6f",
                help="Enter the mass of catalyst in grams"
            )
            
            temperature = st.number_input(
                "Temperature (°C)",
                min_value=-273.15,
                value=float(conditions.get('temperature', 25.0) or 25.0),
                step=1.0,
                format="%.1f"
            )
            
            pressure = st.number_input(
                "Pressure (psi)",
                min_value=0.0,
                value=float(conditions.get('pressure', 14.6959) or 14.6959),
                step=0.1,
                format="%.2f",
                help="Enter the pressure in psi"
            )
            
        
        with col4:
            st.markdown("#### Optional Parameters")
            
            catalyst_percentage = st.number_input(
                "Catalyst %",
                min_value=0.0,
                max_value=100.0,
                value=float(conditions.get('catalyst_percentage', 0.0) or 0.0),
                step=0.1,
                format="%.1f"
            )
            
            water_to_rock_ratio = st.number_input(
                "Water to Rock Ratio",
                min_value=0.0,
                value=float(conditions.get('water_to_rock_ratio', 0.0) or 0.0),
                step=0.1,
                format="%.2f",
                help="Enter the water to rock ratio"
            )

            buffer_system = st.text_input(
                "Buffer System",
                value=conditions.get('buffer_system', ''),
                help="Enter the buffer system used"
            )

            buffer_concentration = st.number_input(
                "Buffer Concentration (mM)",
                min_value=0.0,
                value=float(conditions.get('buffer_concentration', 0.0) or 0.0),
                step=0.1,
                format="%.1f"
            )
            
            initial_nitrate_concentration = st.number_input(
                "Initial Nitrate Concentration (mM)",
                min_value=0.0,
                value=float(conditions.get('initial_nitrate_concentration', 0.0) or 0.0),
                step=0.1,
                format="%.1f"
            )
            
            dissolved_oxygen = st.number_input(
                "Dissolved Oxygen (ppm)",
                min_value=0.0,
                value=float(conditions.get('dissolved_oxygen', 0.0) or 0.0),
                step=0.1,
                format="%.1f"
            )
            
            surfactant_type = st.text_input(
                "Surfactant Type",
                value=conditions.get('surfactant_type', '')
            )
            
            surfactant_concentration = st.number_input(
                "Surfactant Concentration",
                min_value=0.0,
                value=float(conditions.get('surfactant_concentration', 0.0) or 0.0),
                step=0.1,
                format="%.2f"
            )

            flow_rate = st.number_input(
                "Flow Rate (mL/min)",
                min_value=0.0,
                value=float(conditions.get('flow_rate', 0.0) or 0.0),
                step=0.1,
                format="%.1f",
                help="Enter the flow rate in mL/min (optional)"
            )

            co2_partial_pressure = st.number_input(
                "CO2 Partial Pressure (psi)",
                min_value=0.0,
                value=float(conditions.get('co2_partial_pressure', 0.0) or 0.0),
                step=0.1,
                format="%.2f"
            )
            
            confining_pressure = st.number_input(
                "Confining Pressure (psi)",
                min_value=0.0,
                value=float(conditions.get('confining_pressure', 0.0) or 0.0),
                step=0.1,
                format="%.2f"
            )
            
            pore_pressure = st.number_input(
                "Pore Pressure (psi)",
                min_value=0.0,
                value=float(conditions.get('pore_pressure', 0.0) or 0.0),
                step=0.1,
                format="%.2f"
            )
        
        # Prepare data for submission
        form_data = {
            'sample_id': sample_id,
            'researcher': researcher,
            'status': status,
            'date': datetime.datetime.combine(exp_date, datetime.datetime.now().time()),
            'conditions': {
                'particle_size': particle_size,
                'water_to_rock_ratio': water_to_rock_ratio if water_to_rock_ratio > 0 else 0.0,
                'initial_ph': initial_ph,
                'catalyst': catalyst,
                'catalyst_mass': catalyst_mass,
                'catalyst_percentage': catalyst_percentage,
                'temperature': temperature,
                'buffer_system': buffer_system.strip() if buffer_system else '',
                'buffer_concentration': buffer_concentration,
                'pressure': pressure,
                'flow_rate': flow_rate if flow_rate > 0 else None,
                'experiment_type': experiment_type,
                'initial_nitrate_concentration': initial_nitrate_concentration,
                'dissolved_oxygen': dissolved_oxygen,
                'surfactant_type': surfactant_type.strip() if surfactant_type else '',
                'surfactant_concentration': surfactant_concentration,
                'co2_partial_pressure': co2_partial_pressure,
                'confining_pressure': confining_pressure,
                'pore_pressure': pore_pressure
            }
        }
        
        # Submit button
        submit_button = st.form_submit_button("Save Changes")
        if submit_button:
            submit_experiment_edit(experiment['id'], form_data)

def submit_experiment_edit(experiment_id, data):
    """Handle experiment edit form submission."""
    success = update_experiment(experiment_id, data)
    if success:
        st.session_state.edit_mode = False

def update_experiment(experiment_id, data):
    """Update an experiment in the database."""
    try:
        db = SessionLocal()
        
        # Get the experiment
        experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
        
        if experiment is None:
            st.error(f"Experiment with ID {experiment_id} not found.")
            return False
        
        # Log old values before updating
        old_values = {
            'sample_id': experiment.sample_id,
            'researcher': experiment.researcher,
            'status': experiment.status.name,
            'date': experiment.date.isoformat() if experiment.date else None
        }
        
        # Update basic experiment information
        experiment.sample_id = data['sample_id']
        experiment.researcher = data['researcher']
        experiment.status = getattr(ExperimentStatus, data['status'])
        experiment.date = data['date']
        
        # Update or create conditions
        conditions = experiment.conditions
        if conditions:
            # Update existing conditions
            conditions.water_to_rock_ratio = data['conditions']['water_to_rock_ratio']
            conditions.initial_ph = data['conditions']['initial_ph']
            conditions.catalyst = data['conditions']['catalyst']
            conditions.catalyst_percentage = data['conditions']['catalyst_percentage']
            conditions.temperature = data['conditions']['temperature']
            conditions.buffer_system = data['conditions']['buffer_system'].strip() if data['conditions']['buffer_system'] else ''
            conditions.buffer_concentration = data['conditions']['buffer_concentration']
            conditions.pressure = data['conditions']['pressure']
            conditions.flow_rate = data['conditions']['flow_rate']
            conditions.experiment_type = data['conditions']['experiment_type']
            conditions.initial_nitrate_concentration = data['conditions']['initial_nitrate_concentration']
            conditions.dissolved_oxygen = data['conditions']['dissolved_oxygen']
            conditions.surfactant_type = data['conditions']['surfactant_type'].strip() if data['conditions']['surfactant_type'] else ''
            conditions.surfactant_concentration = data['conditions']['surfactant_concentration']
            conditions.co2_partial_pressure = data['conditions']['co2_partial_pressure']
            conditions.confining_pressure = data['conditions']['confining_pressure']
            conditions.pore_pressure = data['conditions']['pore_pressure']
            if hasattr(conditions, 'particle_size'):
                conditions.particle_size = data['conditions']['particle_size']
        else:
            # Create new conditions
            conditions = ExperimentalConditions(
                experiment_id=experiment.id,
                water_to_rock_ratio=data['conditions']['water_to_rock_ratio'],
                initial_ph=data['conditions']['initial_ph'],
                catalyst=data['conditions']['catalyst'],
                catalyst_percentage=data['conditions']['catalyst_percentage'],
                temperature=data['conditions']['temperature'],
                buffer_system=data['conditions']['buffer_system'].strip() if data['conditions']['buffer_system'] else '',
                buffer_concentration=data['conditions']['buffer_concentration'],
                pressure=data['conditions']['pressure'],
                flow_rate=data['conditions']['flow_rate'],
                experiment_type=data['conditions']['experiment_type'],
                initial_nitrate_concentration=data['conditions']['initial_nitrate_concentration'],
                dissolved_oxygen=data['conditions']['dissolved_oxygen'],
                surfactant_type=data['conditions']['surfactant_type'].strip() if data['conditions']['surfactant_type'] else '',
                surfactant_concentration=data['conditions']['surfactant_concentration'],
                co2_partial_pressure=data['conditions']['co2_partial_pressure'],
                confining_pressure=data['conditions']['confining_pressure'],
                pore_pressure=data['conditions']['pore_pressure']
            )
            if hasattr(conditions, 'particle_size'):
                conditions.particle_size = data['conditions']['particle_size']
            db.add(conditions)
        
        # Create a modification log entry
        new_values = {
            'sample_id': data['sample_id'],
            'researcher': data['researcher'],
            'status': data['status'],
            'date': data['date'].isoformat() if data['date'] else None,
            'conditions': data['conditions']
        }
        
        modification = ModificationsLog(
            experiment_id=experiment.id,
            modified_by=data['researcher'],  # Using the researcher as the modifier
            modification_type="update",
            modified_table="experiments",
            old_values=old_values,
            new_values=new_values
        )
        db.add(modification)
        
        # Commit the changes
        db.commit()
        
        # Set a flag in session state to trigger a rerun
        st.session_state.experiment_updated = True
        
        st.success("Experiment updated successfully!")
        return True
    except Exception as e:
        db.rollback()
        st.error(f"Error updating experiment: {str(e)}")
        return False
    finally:
        db.close()
            
def save_results(experiment_id, final_ph, final_nitrate, yield_value):
    """Save experiment results to the database."""
    try:
        db = SessionLocal()
        
        # Check if results exist for this experiment
        result = db.query(ExperimentalResults).filter(ExperimentalResults.experiment_id == experiment_id).first()
        
        # Get user information for the modification log
        user = st.session_state.get('user', {})
        user_identifier = user.get('email', 'Unknown User') if isinstance(user, dict) else 'Unknown User'
        
        if result:
            # Update existing results
            result.final_ph = final_ph
            result.final_nitrate_concentration = final_nitrate
            result.yield_value = yield_value
            
            # Create a modification log entry
            modification = ModificationsLog(
                experiment_id=experiment_id,
                modified_by=user_identifier,
                modification_type="update",
                modified_table="results",
                old_values={
                    'final_ph': result.final_ph,
                    'final_nitrate_concentration': result.final_nitrate_concentration,
                    'yield_value': result.yield_value
                },
                new_values={
                    'final_ph': final_ph,
                    'final_nitrate_concentration': final_nitrate,
                    'yield_value': yield_value
                }
            )
            db.add(modification)
        else:
            # Create new results
            new_result = ExperimentalResults(
                experiment_id=experiment_id,
                final_ph=final_ph,
                final_nitrate_concentration=final_nitrate,
                yield_value=yield_value
            )
            db.add(new_result)
            
            # Create a modification log entry
            modification = ModificationsLog(
                experiment_id=experiment_id,
                modified_by=user_identifier,
                modification_type="create",
                modified_table="results",
                new_values={
                    'final_ph': final_ph,
                    'final_nitrate_concentration': final_nitrate,
                    'yield_value': yield_value
                }
            )
            db.add(modification)
        
        # Commit the changes
        db.commit()
        
        st.success("Results saved successfully!")
        return True
    except Exception as e:
        db.rollback()
        st.error(f"Error saving results: {str(e)}")
        return False
    finally:
        db.close()

def delete_experimental_results(data_id):
    """Delete experimental data from the database."""
    try:
        db = SessionLocal()
        
        # Get the data
        data = db.query(ExperimentalResults).filter(ExperimentalResults.id == data_id).first()
        
        if data is None:
            st.error("Data not found")
            return
        
        # Delete file if it exists
        if data.file_path and os.path.exists(data.file_path):
            try:
                os.remove(data.file_path)
            except OSError as e:
                st.warning(f"Could not delete file: {e}")
        
        # Get user information for the modification log
        user = st.session_state.get('user', {})
        user_identifier = user.get('email', 'Unknown User') if isinstance(user, dict) else 'Unknown User'
        
        # Create a modification log entry
        modification = ModificationsLog(
            experiment_id=data.experiment_id,
            modified_by=user_identifier,
            modification_type="delete",
            modified_table="experimental_results",
            old_values=json.dumps({  # Convert dict to JSON string
                'data_type': data.data_type,
                'description': data.description,
                'data_values': data.data_values
            })
        )
        db.add(modification)
        
        # Delete the data
        db.delete(data)
        
        # Commit the transaction
        db.commit()
        
        st.success("Experimental data deleted successfully!")
        
    except Exception as e:
        db.rollback()
        st.error(f"Error deleting experimental data: {str(e)}")
        raise e
    finally:
        db.close()

def save_experimental_results(experiment_id, data_type, file=None, description=None, data_values=None):
    """Save experimental data to the database."""
    try:
        db = SessionLocal()
        
        # Create a new experimental data entry
        experimental_results = ExperimentalResults(
            experiment_id=experiment_id,
            data_type=data_type,
            description=description,
            data_values=json.dumps(data_values) if data_values else None  # Convert dict to JSON string
        )
        
        # Handle file upload if present
        if file:
            # Create uploads directory if it doesn't exist
            upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads', 'experimental_results')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save file and store path
            file_path = os.path.join(upload_dir, f"{experiment_id}_{file.name}")
            with open(file_path, 'wb') as f:
                f.write(file.getvalue())
            
            experimental_results.file_path = file_path
            experimental_results.file_name = file.name
            experimental_results.file_type = file.type
        
        # Add the data to the session
        db.add(experimental_results)
        
        # Get user information for the modification log
        user = st.session_state.get('user', {})
        user_identifier = user.get('email', 'Unknown User') if isinstance(user, dict) else 'Unknown User'
        
        # Create a modification log entry
        modification = ModificationsLog(
            experiment_id=experiment_id,
            modified_by=user_identifier,
            modification_type="add",
            modified_table="experimental_results",
            new_values=json.dumps({  # Convert dict to JSON string
                'data_type': data_type,
                'description': description,
                'data_values': data_values
            })
        )
        db.add(modification)
        
        # Commit the transaction
        db.commit()
        
        st.success("Experimental data saved successfully!")
        
    except Exception as e:
        db.rollback()
        st.error(f"Error saving experimental data: {str(e)}")
        raise e
    finally:
        db.close()

def delete_external_analysis(analysis_id):
    """Delete external analysis from the database."""
    try:
        db = SessionLocal()
        
        # Get the analysis
        analysis = db.query(ExternalAnalysis).filter(ExternalAnalysis.id == analysis_id).first()
        
        if analysis is None:
            st.error("Analysis not found")
            return
        
        # Delete file if it exists
        if analysis.report_file_path and os.path.exists(analysis.report_file_path):
            os.remove(analysis.report_file_path)
        
        # Get user information for the modification log
        user = st.session_state.get('user', {})
        user_identifier = user.get('email', 'Unknown User') if isinstance(user, dict) else 'Unknown User'
        
        # Create a modification log entry
        modification = ModificationsLog(
            experiment_id=None,  # This is sample-level modification
            modified_by=user_identifier,  # Use email as identifier
            modification_type="delete",
            modified_table="external_analyses",
            old_values={
                'sample_id': analysis.sample_id,
                'analysis_type': analysis.analysis_type,
                'laboratory': analysis.laboratory,
                'analyst': analysis.analyst,
                'analysis_date': analysis.analysis_date.isoformat() if analysis.analysis_date else None,
                'description': analysis.description
            }
        )
        db.add(modification)
        
        # Delete the analysis
        db.delete(analysis)
        
        # Commit the transaction
        db.commit()
        
        st.success("External analysis deleted successfully!")
        
    except Exception as e:
        db.rollback()
        st.error(f"Error deleting external analysis: {str(e)}")
        raise e
    finally:
        db.close()

def save_note(experiment_id, note_text):
    """Save a new note to the database."""
    try:
        db = SessionLocal()
        
        # Create a new note
        note = ExperimentNotes(
            experiment_id=experiment_id,
            note_text=note_text.strip()
        )
        
        # Add the note to the session
        db.add(note)
        
        # Commit the transaction
        db.commit()
        
        st.success("Note saved successfully!")
        
    except Exception as e:
        db.rollback()
        st.error(f"Error saving note: {str(e)}")
        raise e
    finally:
        db.close()

def submit_note_edit(note_id, edited_text):
    """Handle note edit submission."""
    if not edited_text.strip():
        st.error("Note text cannot be empty")
        return
    
    update_note(note_id, edited_text)
    st.session_state.note_form_state['editing_note_id'] = None

def update_note(note_id, note_text):
    """Update an existing note in the database."""
    try:
        db = SessionLocal()
        
        # Get the note
        note = db.query(ExperimentNotes).filter(ExperimentNotes.id == note_id).first()
        
        if note is None:
            st.error("Note not found")
            return
        
        # Update the note
        note.note_text = note_text.strip()
        
        # Commit the transaction
        db.commit()
        
        st.success("Note updated successfully!")
        
    except Exception as e:
        db.rollback()
        st.error(f"Error updating note: {str(e)}")
        raise e
    finally:
        db.close()