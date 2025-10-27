"""
Tests for the experiment lineage migration.

This module tests the establish_experiment_lineage_006 data migration to ensure
it correctly identifies and links experiment derivations.
"""
import os
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, date

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import Base
from database.models import Experiment, ExperimentalConditions
from database.lineage_utils import parse_experiment_id, get_or_find_parent_experiment
from tests.snapshot import DatabaseSnapshot, get_experiment_lineage_info, print_lineage_report


class TestExperimentLineageMigration:
    """Test suite for experiment lineage migration."""
    
    @pytest.fixture
    def test_db_session(self):
        """Create a test database session with sample data."""
        # Create in-memory database
        engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False})
        Base.metadata.create_all(engine)
        
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = TestingSessionLocal()
        
        yield session
        
        session.close()
    
    @pytest.fixture
    def sample_experiments(self, test_db_session):
        """Create sample experiments with various lineage patterns."""
        experiments_data = [
            # Base experiments
            ("HPHT_MH_001", 1, "Base experiment 1"),
            ("HPHT_MH_002", 2, "Base experiment 2"),
            ("LEACH_MH_001", 3, "Leach experiment"),
            
            # Derivations with existing parents
            ("HPHT_MH_001-2", 4, "First derivation of HPHT_MH_001"),
            ("HPHT_MH_001-3", 5, "Second derivation of HPHT_MH_001"),
            ("HPHT_MH_002-1", 6, "First derivation of HPHT_MH_002"),
            
            # Orphaned derivation (parent doesn't exist)
            ("ORPHANED_EXP_001-1", 7, "Derivation with no parent"),
            
            # Non-derivation with hyphens (to test parsing - last part is NOT numeric)
            ("TEST-SAMPLE-ABC", 8, "Not a derivation, just hyphens"),
        ]
        
        experiments = []
        for exp_id, exp_num, desc in experiments_data:
            exp = Experiment(
                experiment_id=exp_id,
                experiment_number=exp_num,
                status='COMPLETED',
                date=date.today()
            )
            test_db_session.add(exp)
            test_db_session.flush()  # Flush to get the ID before setting description
            
            # Set description using the property (creates a note)
            exp.description = desc
            
            experiments.append(exp)
        
        test_db_session.commit()
        
        # Refresh to get IDs
        for exp in experiments:
            test_db_session.refresh(exp)
        
        return experiments
    
    def test_description_property(self, test_db_session):
        """Test that the description property works correctly."""
        # Create an experiment
        exp = Experiment(
            experiment_id="TEST_DESC_001",
            experiment_number=999,
            status='COMPLETED',
            date=date.today()
        )
        test_db_session.add(exp)
        test_db_session.flush()
        
        # Initially, description should be None (no notes)
        assert exp.description is None
        
        # Set description - should create a note
        exp.description = "This is a test description"
        test_db_session.commit()
        test_db_session.refresh(exp)
        
        # Verify description is returned
        assert exp.description == "This is a test description"
        
        # Verify a note was created
        assert len(exp.notes) == 1
        assert exp.notes[0].note_text == "This is a test description"
        
        # Update description - should update the first note
        exp.description = "Updated description"
        test_db_session.commit()
        test_db_session.refresh(exp)
        
        assert exp.description == "Updated description"
        assert len(exp.notes) == 1  # Still only one note
        assert exp.notes[0].note_text == "Updated description"
    
    def test_parse_experiment_id(self):
        """Test parsing of experiment IDs to identify derivations."""
        # Test base experiments
        assert parse_experiment_id("HPHT_MH_001") == ("HPHT_MH_001", None)
        assert parse_experiment_id("LEACH_TEST") == ("LEACH_TEST", None)
        
        # Test derivations
        assert parse_experiment_id("HPHT_MH_001-2") == ("HPHT_MH_001", 2)
        assert parse_experiment_id("HPHT_MH_001-10") == ("HPHT_MH_001", 10)
        assert parse_experiment_id("COMPLEX-ID-TEST-3") == ("COMPLEX-ID-TEST", 3)
        
        # Test IDs that end with numbers (these ARE derivations by design)
        assert parse_experiment_id("TEST-SAMPLE-001") == ("TEST-SAMPLE", 1)
        
        # Test non-derivations with hyphens (last part is NOT numeric)
        assert parse_experiment_id("TEST-SAMPLE-ABC") == ("TEST-SAMPLE-ABC", None)
        assert parse_experiment_id("HPHT-HIGH-TEMP") == ("HPHT-HIGH-TEMP", None)
        
        # Test edge cases
        assert parse_experiment_id("") == (None, None)
        assert parse_experiment_id(None) == (None, None)
        assert parse_experiment_id("   ") == (None, None)
    
    def test_get_or_find_parent_experiment(self, test_db_session, sample_experiments):
        """Test finding parent experiments for derivations."""
        # Test finding existing parent
        parent = get_or_find_parent_experiment(test_db_session, "HPHT_MH_001-2")
        assert parent is not None
        assert parent.experiment_id == "HPHT_MH_001"
        
        # Test finding parent with different derivation number
        parent = get_or_find_parent_experiment(test_db_session, "HPHT_MH_001-3")
        assert parent is not None
        assert parent.experiment_id == "HPHT_MH_001"
        
        # Test orphaned derivation (parent doesn't exist)
        parent = get_or_find_parent_experiment(test_db_session, "ORPHANED_EXP_001-1")
        assert parent is None
        
        # Test base experiment (should return None, not itself)
        parent = get_or_find_parent_experiment(test_db_session, "HPHT_MH_001")
        assert parent is None
    
    def test_lineage_info_extraction(self, test_db_session, sample_experiments):
        """Test extraction of lineage information after fixture setup."""
        lineage_info = get_experiment_lineage_info(test_db_session)
        
        # After fixture creates experiments, lineage is already set by event listeners
        # (Event listeners automatically set lineage when experiments are created)
        assert lineage_info['total_experiments'] == 8
        assert lineage_info['base_experiments'] == 4  # 4 base experiments
        assert lineage_info['derivations'] == 4  # 4 derivations already set by event listeners
        assert lineage_info['linked_derivations'] == 3  # 3 linked (not orphaned)
        assert lineage_info['orphaned_derivations'] == 1  # 1 orphaned
    
    def test_migration_on_sample_data(self, test_db_session, sample_experiments):
        """Test the full migration process on sample data."""
        from database.data_migrations.establish_experiment_lineage_006 import establish_experiment_lineage
        
        # Mock the SessionLocal to use our test session
        import database.data_migrations.establish_experiment_lineage_006 as migration_module
        
        # Create a mock SessionLocal that returns our test session
        class MockSessionLocal:
            def __call__(self):
                return test_db_session
        
        original_session = migration_module.SessionLocal
        migration_module.SessionLocal = MockSessionLocal()
        
        try:
            # Get lineage info before migration
            before_info = get_experiment_lineage_info(test_db_session)
            print("\n=== Before Migration ===")
            print_lineage_report(before_info)
            
            # Run migration in dry-run mode first
            print("\n=== Running Dry Run ===")
            dry_run_summary = establish_experiment_lineage(dry_run=True)
            
            assert dry_run_summary['experiments_scanned'] == 8
            assert dry_run_summary['derivations_found'] == 4  # 3 with parents + 1 orphaned
            
            # Note: In this test, the event listeners already set lineage when experiments
            # were created by the fixture. The migration is idempotent and will re-process
            # them, but the dry-run rollback doesn't affect our shared test session.
            # This is expected behavior - the migration can be run multiple times safely.
            
            # Run actual migration
            print("\n=== Running Actual Migration ===")
            summary = establish_experiment_lineage(dry_run=False)
            
            # Verify summary statistics
            assert summary['experiments_scanned'] == 8
            assert summary['derivations_found'] == 4
            assert summary['parents_linked'] == 3  # HPHT_MH_001-2, HPHT_MH_001-3, HPHT_MH_002-1
            assert summary['orphaned_derivations'] == 1  # ORPHANED_EXP_001-1
            assert summary['errors'] == 0
            
            # Get lineage info after migration
            after_info = get_experiment_lineage_info(test_db_session)
            print("\n=== After Migration ===")
            print_lineage_report(after_info)
            
            # Verify lineage info
            assert after_info['total_experiments'] == 8
            assert after_info['base_experiments'] == 4  # HPHT_MH_001, HPHT_MH_002, LEACH_MH_001, TEST-SAMPLE-ABC
            assert after_info['derivations'] == 4
            assert after_info['linked_derivations'] == 3
            assert after_info['orphaned_derivations'] == 1
            
            # Verify specific experiment lineage
            test_db_session.expire_all()  # Refresh from database
            
            # Check linked derivation
            deriv_1 = test_db_session.query(Experiment).filter_by(experiment_id="HPHT_MH_001-2").first()
            assert deriv_1.base_experiment_id == "HPHT_MH_001"
            assert deriv_1.parent_experiment_fk is not None
            parent_1 = test_db_session.query(Experiment).filter_by(id=deriv_1.parent_experiment_fk).first()
            assert parent_1.experiment_id == "HPHT_MH_001"
            
            # Check another linked derivation
            deriv_2 = test_db_session.query(Experiment).filter_by(experiment_id="HPHT_MH_001-3").first()
            assert deriv_2.base_experiment_id == "HPHT_MH_001"
            assert deriv_2.parent_experiment_fk == parent_1.id  # Same parent as deriv_1
            
            # Check orphaned derivation
            orphaned = test_db_session.query(Experiment).filter_by(experiment_id="ORPHANED_EXP_001-1").first()
            assert orphaned.base_experiment_id == "ORPHANED_EXP_001"
            assert orphaned.parent_experiment_fk is None
            
            # Check non-derivation with hyphens (last part not numeric)
            non_deriv = test_db_session.query(Experiment).filter_by(experiment_id="TEST-SAMPLE-ABC").first()
            assert non_deriv.base_experiment_id is None
            assert non_deriv.parent_experiment_fk is None
            
            print("\n✓ All migration tests passed!")
            
        finally:
            # Restore original SessionLocal
            migration_module.SessionLocal = original_session
    
    def test_migration_idempotency(self, test_db_session, sample_experiments):
        """Test that running the migration multiple times produces the same result."""
        from database.data_migrations.establish_experiment_lineage_006 import establish_experiment_lineage
        
        # Mock the SessionLocal
        import database.data_migrations.establish_experiment_lineage_006 as migration_module
        
        class MockSessionLocal:
            def __call__(self):
                return test_db_session
        
        original_session = migration_module.SessionLocal
        migration_module.SessionLocal = MockSessionLocal()
        
        try:
            # Run migration first time
            summary1 = establish_experiment_lineage(dry_run=False)
            
            # Get state after first run
            info1 = get_experiment_lineage_info(test_db_session)
            
            # Run migration second time
            summary2 = establish_experiment_lineage(dry_run=False)
            
            # Get state after second run
            info2 = get_experiment_lineage_info(test_db_session)
            
            # Verify both runs produce identical results
            assert summary1 == summary2
            assert info1 == info2
            
            print("\n✓ Migration is idempotent - running multiple times produces same result")
            
        finally:
            migration_module.SessionLocal = original_session


def test_snapshot_functionality():
    """Test the database snapshot functionality."""
    # This test requires an actual database file
    test_db_path = "test_migration_snapshot.db"
    engine = None
    temp_engine = None
    
    try:
        # Clean up any existing test database first
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except PermissionError:
                pass  # File locked, will be overwritten
        
        # Create a temporary test database
        engine = create_engine(f'sqlite:///{test_db_path}')
        Base.metadata.create_all(engine)
        
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        
        # Add some test data with unique IDs to avoid conflicts
        import random
        unique_suffix = random.randint(1000, 9999)
        exp = Experiment(
            experiment_id=f"SNAPSHOT_TEST_{unique_suffix}",
            experiment_number=unique_suffix,
            status='COMPLETED',
            date=date.today()
        )
        session.add(exp)
        session.commit()
        session.close()
        
        # Dispose of engine to release file locks
        engine.dispose()
        
        # Test snapshot creation
        snapshot = DatabaseSnapshot(test_db_path)
        
        # Create snapshot
        snapshot_path = snapshot.create_snapshot("test_snapshot")
        assert os.path.exists(snapshot_path)
        
        # Get row counts
        row_counts = snapshot.get_table_row_counts(test_db_path)
        assert 'experiments' in row_counts
        assert row_counts['experiments'] == 1
        
        # Create temp copy
        temp_db_path, temp_url = snapshot.create_temp_copy()
        assert os.path.exists(temp_db_path)
        
        # Modify temp database
        temp_engine = create_engine(temp_url)
        TempSession = sessionmaker(autocommit=False, autoflush=False, bind=temp_engine)
        temp_session = TempSession()
        
        # Add another experiment with unique ID
        exp2 = Experiment(
            experiment_id=f"SNAPSHOT_TEST_{unique_suffix + 1}",
            experiment_number=unique_suffix + 1,
            status='COMPLETED',
            date=date.today()
        )
        temp_session.add(exp2)
        temp_session.commit()
        temp_session.close()
        
        # Dispose of temp engine to release file locks
        temp_engine.dispose()
        
        # Compare databases
        comparison = snapshot.compare_databases(test_db_path, temp_db_path)
        assert not comparison['identical']
        assert 'experiments' in comparison['differences']
        assert comparison['differences']['experiments']['delta'] == 1
        
        # Cleanup
        snapshot.cleanup()
        
        print("\n✓ Snapshot functionality tests passed!")
        
    finally:
        # Dispose engines to release file locks (Windows requirement)
        if engine:
            engine.dispose()
        if temp_engine:
            temp_engine.dispose()
        
        # Small delay for Windows to release file locks
        import time
        time.sleep(0.1)
        
        # Cleanup test files
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except PermissionError:
                pass  # File still locked, skip cleanup
        
        # Clean up snapshot directory
        snapshot_dir = "tests/snapshots"
        if os.path.exists(snapshot_dir):
            import shutil
            try:
                shutil.rmtree(snapshot_dir)
            except PermissionError:
                pass  # Files still locked, skip cleanup


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])

