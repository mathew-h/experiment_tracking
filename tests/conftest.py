import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from database.models import Base, PXRFReading

@pytest.fixture
def test_db() -> Session:
    """Create a test database session for use in tests."""
    # Create an in-memory SQLite database for testing
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool
    )
    
    # Create all tables in the test database
    Base.metadata.create_all(engine)
    
    # Create a session factory
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create a new session for the test
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        # Clean up after the test
        db.close()
        Base.metadata.drop_all(engine)

@pytest.fixture
def pxrf_reading(test_db):
    """Create a sample pXRF reading entry."""
    reading = PXRFReading(
        reading_no="TEST001",
        fe=10.5,
        mg=2.3,
        ni=0.5,
        cu=0.3,
        si=45.2,
        co=0.1,
        mo=0.02,
        al=8.4
    )
    test_db.add(reading)
    test_db.commit()
    return reading 