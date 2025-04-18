import pytest
from datetime import datetime, timezone
from database.models import Sample, PXRFReading, Laboratory, Analyst

def test_create_pxrf_reading(test_db):
    """Test creating a new pXRF reading with complete sample information."""
    # Create test data
    lab = Laboratory(name="Test Lab", location="Test Location")
    analyst = Analyst(name="John Doe", email="john@testlab.com")
    sample = Sample(
        sample_id="TEST-001",
        collection_date=datetime.now(timezone.utc),
        location="Test Site"
    )
    
    test_db.add_all([lab, analyst, sample])
    test_db.commit()
    
    # Create pXRF reading
    reading = PXRFReading(
        sample_id=sample.id,
        reading_date=datetime.now(timezone.utc),
        laboratory_id=lab.id,
        analyst_id=analyst.id,
        fe_content=45.67,
        si_content=12.34,
        al_content=5.67,
        instrument_model="Niton XL3t",
        calibration_date=datetime.now(timezone.utc)
    )
    
    test_db.add(reading)
    test_db.commit()
    
    # Verify the reading was created correctly
    saved_reading = test_db.query(PXRFReading).first()
    assert saved_reading is not None
    assert saved_reading.fe_content == 45.67
    assert saved_reading.si_content == 12.34
    assert saved_reading.al_content == 5.67
    assert saved_reading.sample_id == sample.id
    assert saved_reading.laboratory_id == lab.id
    assert saved_reading.analyst_id == analyst.id

def test_multiple_readings_per_sample(test_db):
    """Test creating multiple pXRF readings for the same sample."""
    # Create base data
    lab = Laboratory(name="Test Lab", location="Test Location")
    analyst = Analyst(name="Jane Smith", email="jane@testlab.com")
    sample = Sample(
        sample_id="TEST-002",
        collection_date=datetime.now(timezone.utc),
        location="Test Site B"
    )
    
    test_db.add_all([lab, analyst, sample])
    test_db.commit()
    
    # Create multiple readings
    readings = [
        PXRFReading(
            sample_id=sample.id,
            reading_date=datetime.now(timezone.utc),
            laboratory_id=lab.id,
            analyst_id=analyst.id,
            fe_content=val,
            si_content=val/2,
            al_content=val/3,
            instrument_model="Niton XL3t",
            calibration_date=datetime.now(timezone.utc)
        )
        for val in [42.1, 43.2, 41.9]  # Three readings with different values
    ]
    
    test_db.add_all(readings)
    test_db.commit()
    
    # Verify all readings were saved
    saved_readings = test_db.query(PXRFReading).filter_by(sample_id=sample.id).all()
    assert len(saved_readings) == 3
    assert all(reading.sample_id == sample.id for reading in saved_readings)
    assert len({reading.fe_content for reading in saved_readings}) == 3  # All values are different

def test_invalid_reading_values(test_db):
    """Test validation of pXRF reading values."""
    lab = Laboratory(name="Test Lab", location="Test Location")
    analyst = Analyst(name="Bob Wilson", email="bob@testlab.com")
    sample = Sample(
        sample_id="TEST-003",
        collection_date=datetime.now(timezone.utc),
        location="Test Site C"
    )
    
    test_db.add_all([lab, analyst, sample])
    test_db.commit()
    
    # Test with invalid negative values
    with pytest.raises(ValueError):
        reading = PXRFReading(
            sample_id=sample.id,
            reading_date=datetime.now(timezone.utc),
            laboratory_id=lab.id,
            analyst_id=analyst.id,
            fe_content=-1.0,  # Invalid negative value
            si_content=10.0,
            al_content=5.0,
            instrument_model="Niton XL3t",
            calibration_date=datetime.now(timezone.utc)
        )
        test_db.add(reading)
        test_db.commit()

def test_reading_relationships(test_db):
    """Test the relationships between PXRFReading and related entities."""
    # Create test data
    lab = Laboratory(name="Test Lab", location="Test Location")
    analyst = Analyst(name="Alice Johnson", email="alice@testlab.com")
    sample = Sample(
        sample_id="TEST-004",
        collection_date=datetime.now(timezone.utc),
        location="Test Site D"
    )
    
    test_db.add_all([lab, analyst, sample])
    test_db.commit()
    
    # Create reading with relationships
    reading = PXRFReading(
        sample_id=sample.id,
        reading_date=datetime.now(timezone.utc),
        laboratory_id=lab.id,
        analyst_id=analyst.id,
        fe_content=55.5,
        si_content=22.2,
        al_content=11.1,
        instrument_model="Niton XL3t",
        calibration_date=datetime.now(timezone.utc)
    )
    
    test_db.add(reading)
    test_db.commit()
    
    # Verify relationships
    saved_reading = test_db.query(PXRFReading).first()
    assert saved_reading.sample.sample_id == "TEST-004"
    assert saved_reading.laboratory.name == "Test Lab"
    assert saved_reading.analyst.name == "Alice Johnson" 