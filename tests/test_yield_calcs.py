# DISABLED: This test file tests NMRResults model and nmr_data relationships that no longer exist in the new modular structure
# The current structure uses ScalarResults directly without separate NMR models

# from sqlalchemy.orm import Session
# import pytest
# from database.models import Experiment, ExperimentalResults, ScalarResults, ExperimentalConditions

# Test calculation when calling calculate_yields() directly
def test_grams_per_ton_yield_calculation(test_db: Session, test_scalar_result: ScalarResults):
    """Test that grams_per_ton_yield is calculated correctly when calculate_yields is called."""
    scalar_result = test_scalar_result
    nmr_result = scalar_result.result_entry.nmr_data # Should exist from fixtures
    conditions = scalar_result.result_entry.experiment.conditions

    # Ensure preconditions
    assert nmr_result is not None
    assert conditions is not None
    assert conditions.rock_mass is not None and conditions.rock_mass > 0
    assert conditions.water_volume is not None

    # Manually set ammonia_mass_g for testing this specific calculation
    # This bypasses the NMR calculation logic for this test
    test_ammonia_mass_g = 0.01804 # Example: 1 mmol in 1 L water
    nmr_result.ammonia_mass_g = test_ammonia_mass_g
    test_db.commit()
    test_db.refresh(nmr_result)

    # Manually set rock mass using test_db
    test_rock_mass_g = 50.0
    conditions.rock_mass = test_rock_mass_g
    test_db.commit()
    test_db.refresh(conditions)

    # Call the calculation method
    scalar_result.calculate_yields()
    test_db.commit() # Save the result of calculation
    test_db.refresh(scalar_result)

    # Expected calculation: 1e6 * (ammonia_mass_g / rock_mass_g)
    expected_yield = 1_000_000 * (test_ammonia_mass_g / test_rock_mass_g)

    assert scalar_result.grams_per_ton_yield == pytest.approx(expected_yield)

# Test calculation when a new NMRResult is added/calculated
def test_yield_calculation_on_nmr_update(test_db: Session, test_scalar_result: ScalarResults):
    """Test that grams_per_ton_yield is calculated when NMRResults.calculate_values is called."""
    scalar_result = test_scalar_result
    exp_result = scalar_result.result_entry
    conditions = exp_result.experiment.conditions

    # Ensure preconditions
    assert conditions is not None
    assert conditions.rock_mass == 100.0 # From fixture
    assert conditions.water_volume == 500.0 # From fixture
    assert scalar_result.grams_per_ton_yield is None # Should be None initially

    # Create a *new* NMR result associated with the existing experimental result
    # The fixture already created one, but let's simulate adding/updating data fully
    # If an NMR result already exists, update it; otherwise, create a new one
    nmr_result = exp_result.nmr_data
    if nmr_result is None:
        nmr_result = NMRResults(result_id=exp_result.id)
        exp_result.nmr_data = nmr_result
        test_db.add(nmr_result)

    # Update NMR input values that affect ammonia_mass_g
    nmr_result.is_concentration_mm = 0.0263 # Default
    nmr_result.is_protons = 2 # Default
    nmr_result.sampled_rxn_volume_ul = 476.0 # Default
    nmr_result.nmr_total_volume_ul = 647.0 # Default
    nmr_result.nh4_peak_area_1 = 2.0 # Set a peak area
    nmr_result.nh4_peak_area_2 = None
    nmr_result.nh4_peak_area_3 = None

    # Call NMR calculation, which should trigger ScalarResults.calculate_yields
    nmr_result.calculate_values()
    test_db.commit()
    test_db.refresh(scalar_result)
    test_db.refresh(nmr_result)

    # Verify NMR calculation happened
    assert nmr_result.total_nh4_peak_area == pytest.approx(2.0)
    assert nmr_result.ammonium_concentration_mm is not None
    assert nmr_result.ammonia_mass_g is not None

    # Expected yield calculation based on the NMR results and conditions
    expected_yield = 1_000_000 * (nmr_result.ammonia_mass_g / conditions.rock_mass)

    assert scalar_result.grams_per_ton_yield is not None
    assert scalar_result.grams_per_ton_yield == pytest.approx(expected_yield)

# Test edge case: rock_mass is zero
def test_yield_calculation_zero_rock_mass(test_db: Session, test_scalar_result: ScalarResults):
    """Test yield calculation results in None if rock_mass is zero."""
    scalar_result = test_scalar_result
    nmr_result = scalar_result.result_entry.nmr_data
    conditions = scalar_result.result_entry.experiment.conditions

    # Set ammonia_mass_g
    nmr_result.ammonia_mass_g = 0.01
    # Set rock_mass to zero
    conditions.rock_mass = 0.0
    test_db.commit()

    scalar_result.calculate_yields()
    test_db.commit()
    test_db.refresh(scalar_result)

    assert scalar_result.grams_per_ton_yield is None

# Test edge case: rock_mass is None
def test_yield_calculation_none_rock_mass(test_db: Session, test_scalar_result: ScalarResults):
    """Test yield calculation results in None if rock_mass is None."""
    scalar_result = test_scalar_result
    nmr_result = scalar_result.result_entry.nmr_data
    conditions = scalar_result.result_entry.experiment.conditions

    # Set ammonia_mass_g
    nmr_result.ammonia_mass_g = 0.01
    # Set rock_mass to None
    conditions.rock_mass = None
    test_db.commit()

    scalar_result.calculate_yields()
    test_db.commit()
    test_db.refresh(scalar_result)

    assert scalar_result.grams_per_ton_yield is None

# Test edge case: ammonia_mass_g is None
def test_yield_calculation_none_ammonia_mass(test_db: Session, test_scalar_result: ScalarResults):
    """Test yield calculation results in None if ammonia_mass_g is None."""
    scalar_result = test_scalar_result
    nmr_result = scalar_result.result_entry.nmr_data
    conditions = scalar_result.result_entry.experiment.conditions

    # Set ammonia_mass_g to None
    nmr_result.ammonia_mass_g = None
    # Ensure rock_mass is valid
    conditions.rock_mass = 100.0
    test_db.commit()

    scalar_result.calculate_yields()
    test_db.commit()
    test_db.refresh(scalar_result)

    assert scalar_result.grams_per_ton_yield is None
