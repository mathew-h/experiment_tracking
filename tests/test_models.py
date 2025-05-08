import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, Experiment, ExperimentalResults, NMRResults, SampleInfo, ExternalAnalysis, PXRFReading, ExperimentStatus, ResultType
from datetime import datetime

# Configure the test database (in-memory SQLite)
DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """Fixture to create and teardown database tables for each test function."""
    Base.metadata.create_all(bind=engine)  # Create tables
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)  # Drop tables

def test_experiment_cascade_delete(db_session):
    """Test that deleting an Experiment cascades to related ExperimentalResults and NMRResults."""
    # 1. Create an Experiment
    experiment = Experiment(
        experiment_id="EXP-001",
        experiment_number=1,
        researcher="Test Researcher",
        date=datetime.now(),
        status=ExperimentStatus.PLANNED
    )
    db_session.add(experiment)
    db_session.commit()
    db_session.refresh(experiment) # Get the generated ID

    # 2. Create ExperimentalResults linked to the Experiment
    exp_result = ExperimentalResults(
        experiment_fk=experiment.id,
        experiment_id=experiment.experiment_id,
        time_post_reaction=1.0,
        result_type=ResultType.NMR,
        description="Initial NMR results"
    )
    db_session.add(exp_result)
    db_session.commit()
    db_session.refresh(exp_result)

    # 3. Create NMRResults linked to ExperimentalResults
    nmr_result = NMRResults(
        result_id=exp_result.id,
        is_concentration_mm=0.025,
        is_protons=2,
        sampled_rxn_volume_ul=500,
        nmr_total_volume_ul=650,
        nh4_peak_area_1=100.0
    )
    # Link NMRResults to ExperimentalResults manually if needed (though relationship should handle it)
    exp_result.nmr_data = nmr_result
    db_session.add(nmr_result)
    db_session.commit()

    # Verify creation
    assert db_session.query(Experiment).count() == 1
    assert db_session.query(ExperimentalResults).count() == 1
    assert db_session.query(NMRResults).count() == 1
    assert db_session.query(ExperimentalResults).first().nmr_data is not None

    # 4. Delete the Experiment
    db_session.delete(experiment)
    db_session.commit()

    # 5. Assert all children are gone
    assert db_session.query(Experiment).count() == 0
    assert db_session.query(ExperimentalResults).count() == 0
    assert db_session.query(NMRResults).count() == 0


def test_sample_info_cascade_delete(db_session):
    """Test that deleting SampleInfo cascades to ExternalAnalysis, but sets FK null in PXRFReading."""
    # 1. Create SampleInfo
    sample = SampleInfo(
        sample_id="SAMPLE-001",
        rock_classification="Test Rock",
        state="Test State",
        country="Test Country"
    )
    db_session.add(sample)
    db_session.commit()

    # 2. Create PXRFReading
    pxrf = PXRFReading(
        reading_no="PXRF-001",
        fe=10.5,
        mg=5.2
    )
    db_session.add(pxrf)
    db_session.commit()

    # 3. Create ExternalAnalysis linked to SampleInfo and PXRFReading
    analysis = ExternalAnalysis(
        sample_id=sample.sample_id,
        analysis_type="PXRF",
        analysis_date=datetime.now(),
        pxrf_reading_no=pxrf.reading_no # Link to PXRF reading
    )
    db_session.add(analysis)
    db_session.commit()
    db_session.refresh(analysis) # Get the generated ID

    # Verify creation
    assert db_session.query(SampleInfo).count() == 1
    assert db_session.query(ExternalAnalysis).count() == 1
    assert db_session.query(PXRFReading).count() == 1
    assert db_session.query(ExternalAnalysis).first().pxrf_reading is not None

    # 4. Delete the SampleInfo
    db_session.delete(sample)
    db_session.commit()

    # 5. Assert cascade works for ExternalAnalysis, but PXRFReading remains (with null FK in ExternalAnalysis)
    assert db_session.query(SampleInfo).count() == 0
    assert db_session.query(ExternalAnalysis).count() == 0

    # Check that PXRFReading still exists
    assert db_session.query(PXRFReading).count() == 1
    pxrf_after_delete = db_session.query(PXRFReading).first()
    assert pxrf_after_delete is not None
    assert pxrf_after_delete.reading_no == "PXRF-001"

    # Because ExternalAnalysis was deleted via cascade from SampleInfo, there are no ExternalAnalysis rows
    # referencing the PXRFReading anymore. The relationship pxrf_reading.external_analyses should be empty.
    assert len(pxrf_after_delete.external_analyses) == 0
