"""
Tests for the Timepoint Brine Modifications bulk upload service and the
associated model changes.

Covered scenarios
-----------------
1. Normal import          – matched row gets description written; flag = True
2. Unmatched experiment   – error surfaced in feedback, row not written
3. Unmatched timepoint    – error surfaced in feedback, row not written
4. Duplicate rows         – rejected in strict mode (no overwrite); flagged
5. Overwrite behaviour    – blank + overwrite=True clears field
6. Blank modification skip – blank + overwrite=False → row skipped
7. has_brine_modification sync  – ORM validator keeps flag in sync
8. has_h2_measurement property  – non-null h2_concentration → True; None → False
"""
import io
import os
import sys

import pytest
import pandas as pd

# Ensure project root is on path regardless of how pytest is invoked
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import (
    Base, Experiment, ExperimentalConditions,
    ExperimentalResults, ScalarResults,
)
from database.models.enums import ExperimentStatus
from backend.services.bulk_uploads.timepoint_modifications import (
    TimepointModificationsUploadService,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_csv(rows: list[dict]) -> bytes:
    """Convert a list of dicts to CSV bytes."""
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def _call(db, rows, *, overwrite_all=False, dry_run=False, filename="test.csv"):
    return TimepointModificationsUploadService.bulk_upsert_from_file(
        db=db,
        file_bytes=_make_csv(rows),
        filename=filename,
        overwrite_all=overwrite_all,
        dry_run=dry_run,
        modified_by="test_user",
    )


# ---------------------------------------------------------------------------
# Fixtures — re-use conftest fixtures where possible; define extras here
# ---------------------------------------------------------------------------

@pytest.fixture
def exp_with_result(test_db):
    """
    Experiment 'MOD_TEST_001' with a single ExperimentalResults row at day 7.
    Returns (experiment, result_row).
    """
    import datetime

    conditions = ExperimentalConditions(
        experiment_id="MOD_TEST_001",
        rock_mass_g=50.0,
        water_volume_mL=200.0,
        temperature_c=25.0,
    )
    exp = Experiment(
        experiment_id="MOD_TEST_001",
        experiment_number=901,
        date=datetime.date.today(),
        status=ExperimentStatus.ONGOING,
    )
    exp.conditions = conditions
    test_db.add(exp)
    test_db.flush()

    conditions.experiment_fk = exp.id
    conditions.experiment_id = exp.experiment_id

    result = ExperimentalResults(
        experiment_fk=exp.id,
        time_post_reaction_days=7.0,
        time_post_reaction_bucket_days=7.0,
        is_primary_timepoint_result=True,
        description="Day 7 sample",
    )
    test_db.add(result)
    test_db.commit()
    test_db.refresh(exp)
    test_db.refresh(result)
    return exp, result


# ---------------------------------------------------------------------------
# Test 1: Normal import
# ---------------------------------------------------------------------------

def test_normal_import_writes_description_and_sets_flag(test_db, exp_with_result):
    """A matched row should have its description written and has_brine_modification=True."""
    exp, result = exp_with_result

    updated, skipped, errors, feedbacks = _call(
        test_db,
        [{"experiment_id": "MOD_TEST_001", "time_point": 7.0,
          "experiment_modification": "Added 5 mL DI water"}],
    )

    assert errors == [], f"Unexpected errors: {errors}"
    assert updated == 1
    assert skipped == 0

    test_db.refresh(result)
    assert result.brine_modification_description == "Added 5 mL DI water"
    assert result.has_brine_modification is True

    fb = feedbacks[0]
    assert fb["status"] == "updated"
    assert fb["result_id"] == result.id
    assert fb["new_value"] == "Added 5 mL DI water"


# ---------------------------------------------------------------------------
# Test 2: Unmatched experiment ID
# ---------------------------------------------------------------------------

def test_unmatched_experiment_id_surfaces_error(test_db):
    """An experiment_id that does not exist should produce an error feedback row."""
    updated, skipped, errors, feedbacks = _call(
        test_db,
        [{"experiment_id": "DOES_NOT_EXIST", "time_point": 7.0,
          "experiment_modification": "Something"}],
    )

    assert updated == 0
    # Should have at least one error string
    assert any("DOES_NOT_EXIST" in e for e in errors) or any(
        "DOES_NOT_EXIST" in " ".join(fb["errors"]) for fb in feedbacks
    )
    fb = feedbacks[0]
    assert fb["status"] == "error"


# ---------------------------------------------------------------------------
# Test 3: Unmatched timepoint
# ---------------------------------------------------------------------------

def test_unmatched_timepoint_surfaces_error(test_db, exp_with_result):
    """A time_point with no matching experimental_results row should error."""
    exp, result = exp_with_result

    updated, skipped, errors, feedbacks = _call(
        test_db,
        [{"experiment_id": "MOD_TEST_001", "time_point": 999.0,
          "experiment_modification": "Something"}],
    )

    assert updated == 0
    fb = feedbacks[0]
    assert fb["status"] == "error"
    assert any("999" in e for e in (errors + fb["errors"]))


# ---------------------------------------------------------------------------
# Test 4: Duplicate rows in upload — strict mode rejection
# ---------------------------------------------------------------------------

def test_duplicate_rows_rejected_in_strict_mode(test_db, exp_with_result):
    """Two rows for the same (experiment_id, time_point) without overwrite → rejected."""
    _, _ = exp_with_result

    rows = [
        {"experiment_id": "MOD_TEST_001", "time_point": 7.0,
         "experiment_modification": "First write"},
        {"experiment_id": "MOD_TEST_001", "time_point": 7.0,
         "experiment_modification": "Second write"},
    ]
    updated, skipped, errors, feedbacks = _call(test_db, rows, overwrite_all=False)

    assert updated == 0
    assert any("Duplicate" in e or "duplicate" in e for e in errors)


def test_duplicate_rows_allowed_when_overwrite_true(test_db, exp_with_result):
    """Duplicate rows with overwrite=true → last-row-wins, no rejection."""
    _, result = exp_with_result

    rows = [
        {"experiment_id": "MOD_TEST_001", "time_point": 7.0,
         "experiment_modification": "First write", "overwrite_existing": "true"},
        {"experiment_id": "MOD_TEST_001", "time_point": 7.0,
         "experiment_modification": "Second write", "overwrite_existing": "true"},
    ]
    updated, skipped, errors, feedbacks = _call(test_db, rows, overwrite_all=False)

    # No hard duplicate rejection errors
    dup_errors = [e for e in errors if "Duplicate" in e or "duplicate" in e]
    assert dup_errors == [], f"Unexpected duplicate errors: {dup_errors}"
    assert updated == 2  # both rows written (last one wins in DB)

    test_db.refresh(result)
    assert result.brine_modification_description == "Second write"


# ---------------------------------------------------------------------------
# Test 5: Overwrite behaviour — blank + overwrite=True clears field
# ---------------------------------------------------------------------------

def test_blank_modification_with_overwrite_true_clears_field(test_db, exp_with_result):
    """Blank experiment_modification with overwrite_existing=true should clear the field."""
    _, result = exp_with_result

    # First write a description
    result.brine_modification_description = "Existing note"
    test_db.commit()
    test_db.refresh(result)
    assert result.has_brine_modification is True

    # Now send blank row with overwrite=true
    updated, skipped, errors, feedbacks = _call(
        test_db,
        [{"experiment_id": "MOD_TEST_001", "time_point": 7.0,
          "experiment_modification": "", "overwrite_existing": "true"}],
    )

    assert errors == []
    test_db.refresh(result)
    assert result.brine_modification_description is None
    assert result.has_brine_modification is False


# ---------------------------------------------------------------------------
# Test 6: Blank modification skip — no overwrite
# ---------------------------------------------------------------------------

def test_blank_modification_without_overwrite_skips_row(test_db, exp_with_result):
    """Blank experiment_modification without overwrite should skip the row."""
    _, result = exp_with_result

    updated, skipped, errors, feedbacks = _call(
        test_db,
        [{"experiment_id": "MOD_TEST_001", "time_point": 7.0,
          "experiment_modification": ""}],
        overwrite_all=False,
    )

    assert errors == []
    assert updated == 0
    assert skipped == 1
    fb = feedbacks[0]
    assert fb["status"] == "skipped"

    test_db.refresh(result)
    assert result.brine_modification_description is None
    assert result.has_brine_modification is False


# ---------------------------------------------------------------------------
# Test 7: has_brine_modification sync via ORM validator
# ---------------------------------------------------------------------------

def test_has_brine_modification_syncs_when_set(test_db, exp_with_result):
    """Setting brine_modification_description should auto-toggle has_brine_modification."""
    _, result = exp_with_result

    # Default state
    assert result.brine_modification_description is None
    assert result.has_brine_modification is False

    # Set a non-blank description
    result.brine_modification_description = "Added catalyst"
    test_db.commit()
    test_db.refresh(result)
    assert result.has_brine_modification is True

    # Clear the description
    result.brine_modification_description = None
    test_db.commit()
    test_db.refresh(result)
    assert result.has_brine_modification is False


def test_has_brine_modification_whitespace_only_is_false(test_db, exp_with_result):
    """A whitespace-only description should not set has_brine_modification to True."""
    _, result = exp_with_result

    result.brine_modification_description = "   "
    test_db.commit()
    test_db.refresh(result)
    assert result.has_brine_modification is False


# ---------------------------------------------------------------------------
# Test 8: has_h2_measurement property
# ---------------------------------------------------------------------------

def test_has_h2_measurement_true_when_h2_concentration_set(test_db, exp_with_result):
    """has_h2_measurement should be True when h2_concentration is not None."""
    _, result = exp_with_result
    scalar = ScalarResults(
        result_id=result.id,
        h2_concentration=500.0,
        gas_sampling_volume_ml=10.0,
        gas_sampling_pressure_MPa=0.1,
    )
    test_db.add(scalar)
    test_db.commit()
    test_db.refresh(scalar)

    assert scalar.has_h2_measurement is True


def test_has_h2_measurement_false_when_h2_concentration_none(test_db, exp_with_result):
    """has_h2_measurement should be False when h2_concentration is None."""
    _, result = exp_with_result
    scalar = ScalarResults(
        result_id=result.id,
        final_ph=7.0,
    )
    test_db.add(scalar)
    test_db.commit()
    test_db.refresh(scalar)

    assert scalar.has_h2_measurement is False


def test_has_h2_measurement_false_when_no_scalar_row(test_db, exp_with_result):
    """A result row with no scalar_data attached has no H2 measurement."""
    _, result = exp_with_result
    assert result.scalar_data is None
    # Property lives on ScalarResults; verify we get False from a freshly
    # created ScalarResults with null concentration
    scalar = ScalarResults(result_id=result.id)
    test_db.add(scalar)
    test_db.commit()
    test_db.refresh(scalar)
    assert scalar.has_h2_measurement is False


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------

def test_existing_value_preserved_without_overwrite(test_db, exp_with_result):
    """An existing description should be preserved when overwrite_existing=false."""
    _, result = exp_with_result

    result.brine_modification_description = "Pre-existing note"
    test_db.commit()

    updated, skipped, errors, feedbacks = _call(
        test_db,
        [{"experiment_id": "MOD_TEST_001", "time_point": 7.0,
          "experiment_modification": "New note"}],
        overwrite_all=False,
    )

    assert errors == []
    assert updated == 0
    assert skipped == 1
    test_db.refresh(result)
    assert result.brine_modification_description == "Pre-existing note"


def test_integer_and_float_time_point_match_same_row(test_db, exp_with_result):
    """time_point values '7', '7.0', and 7 should all match the same row."""
    _, result = exp_with_result

    for time_val in ["7", "7.0", 7, 7.0]:
        # Clear between iterations
        result.brine_modification_description = None
        test_db.commit()

        updated, skipped, errors, feedbacks = _call(
            test_db,
            [{"experiment_id": "MOD_TEST_001", "time_point": time_val,
              "experiment_modification": f"Test at {time_val}"}],
        )
        assert errors == [], f"time_val={time_val!r} produced errors: {errors}"
        assert updated == 1, f"time_val={time_val!r}: expected 1 updated"
        test_db.refresh(result)
        assert result.brine_modification_description is not None


def test_dry_run_does_not_write(test_db, exp_with_result):
    """dry_run=True must not modify any rows in the database."""
    _, result = exp_with_result

    _call(
        test_db,
        [{"experiment_id": "MOD_TEST_001", "time_point": 7.0,
          "experiment_modification": "Dry run note"}],
        dry_run=True,
    )

    test_db.refresh(result)
    assert result.brine_modification_description is None
    assert result.has_brine_modification is False
