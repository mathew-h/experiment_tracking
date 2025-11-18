# Test Fixes Applied

## Issues Found and Resolved

### Issue 1: `'description' is an invalid keyword argument for Experiment`

**Problem:**
The test was trying to create `Experiment` objects with a `description` parameter, but the `Experiment` model doesn't have a `description` column.

**Root Cause:**
The `Experiment` model in `database/models/experiments.py` only has these fields:
- `id`
- `experiment_id`
- `experiment_number`
- `sample_id`
- `researcher`
- `date`
- `status`
- `created_at`
- `updated_at`
- `base_experiment_id` (lineage)
- `parent_experiment_fk` (lineage)

There is no `description` field.

**Fix:**
Removed the `description` parameter from all test experiment creation. The tests now create experiments with only valid fields:

```python
exp = Experiment(
    experiment_id=exp_id,
    experiment_number=exp_num,
    status='COMPLETED',
    date=date.today()
)
```

**Files Changed:**
- `tests/test_lineage_migration.py` - Updated `sample_experiments` fixture

---

### Issue 2: `PermissionError: The process cannot access the file` (Windows)

**Problem:**
On Windows, SQLite database files remain locked even after closing sessions, preventing cleanup operations from deleting test files.

**Root Cause:**
SQLAlchemy's engine maintains connection pools that keep file handles open. On Windows, you cannot delete a file that has any open handles, even if sessions are closed.

**Fix:**
Added proper engine disposal and error handling:

1. **Explicitly dispose engines** before cleanup:
   ```python
   engine.dispose()
   temp_engine.dispose()
   ```

2. **Added a small delay** for Windows to release locks:
   ```python
   import time
   time.sleep(0.1)
   ```

3. **Wrapped cleanup in try-except** to handle locked files gracefully:
   ```python
   try:
       os.remove(test_db_path)
   except PermissionError:
       pass  # File still locked, skip cleanup
   ```

**Files Changed:**
- `tests/test_lineage_migration.py` - Updated `test_snapshot_functionality()` function

---

## Test Status After Fixes

After applying these fixes, all tests should pass:

- ✅ `test_parse_experiment_id` - ID parsing logic
- ✅ `test_get_or_find_parent_experiment` - Parent finding
- ✅ `test_lineage_info_extraction` - Lineage info extraction
- ✅ `test_migration_on_sample_data` - Full migration test
- ✅ `test_migration_idempotency` - Idempotency verification
- ✅ `test_snapshot_functionality` - Snapshot utilities

## Running the Tests

```bash
# Run all tests
python -m pytest tests/test_lineage_migration.py -v -s

# Run specific test
python -m pytest tests/test_lineage_migration.py::TestExperimentLineageMigration::test_migration_on_sample_data -v
```

## Notes for Future Test Development

1. **Always check the model** before creating test objects - use only fields that exist in the SQLAlchemy model
2. **Dispose SQLAlchemy engines** in test cleanup, especially on Windows
3. **Use try-except for cleanup** to make tests more robust
4. **Add small delays** if needed for OS to release file locks on Windows

## Additional Improvements Made

- Better error handling in cleanup
- More explicit engine lifecycle management
- Comments explaining Windows-specific requirements
- Graceful handling of locked files

