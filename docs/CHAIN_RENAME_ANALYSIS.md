# Chain Rename Analysis: Your Specific Scenario

## Your Question

Can the renaming logic handle this scenario without breaking?

```
HPHT_MH_036   -> HPHT_MH_036
HPHT_MH_036-2 -> HPHT_MH_036_Desorption
HPHT_MH_036-5 -> HPHT_MH_036-2
```

## Answer

**Yes, but ONLY if processed in the correct order.**

## The Issue

This is a "chain rename" where:
- `HPHT_MH_036-2` is renamed to `HPHT_MH_036_Desorption`
- `HPHT_MH_036-5` is renamed to `HPHT_MH_036-2` (reusing the freed-up name)

The new ID of one experiment (`HPHT_MH_036-2`) is the old ID of another experiment.

## What Happens

### ✅ CORRECT Order (as shown above)

**Excel Sheet:**
```excel
Row 1: experiment_id=HPHT_MH_036,            old_experiment_id=HPHT_MH_036,   overwrite=TRUE
Row 2: experiment_id=HPHT_MH_036_Desorption, old_experiment_id=HPHT_MH_036-2, overwrite=TRUE
Row 3: experiment_id=HPHT_MH_036-2,          old_experiment_id=HPHT_MH_036-5, overwrite=TRUE
```

**Processing:**
1. Row 1: No rename (same ID), just update - **SUCCESS**
2. Row 2: Rename `HPHT_MH_036-2` → `HPHT_MH_036_Desorption` - **SUCCESS**
   - ID `HPHT_MH_036-2` is now freed up
3. Row 3: Rename `HPHT_MH_036-5` → `HPHT_MH_036-2` - **SUCCESS**
   - Uses the freed-up ID from step 2

**Result:** ✅ All three experiments successfully processed

### ❌ WRONG Order

**Excel Sheet:**
```excel
Row 1: experiment_id=HPHT_MH_036-2,          old_experiment_id=HPHT_MH_036-5, overwrite=TRUE
Row 2: experiment_id=HPHT_MH_036_Desorption, old_experiment_id=HPHT_MH_036-2, overwrite=TRUE
```

**Processing:**
1. Row 1: Rename `HPHT_MH_036-5` → `HPHT_MH_036-2` - **SUCCESS**
   - Experiment that was `-5` is now `-2`
2. Row 2: Try to find experiment with old_id `HPHT_MH_036-2` - **PROBLEM**
   - The ORIGINAL `-2` experiment still exists (hasn't been renamed yet)
   - System finds it and renames it to `_Desorption` - **SUCCESS** but...
   - Now we have TWO experiments fighting for the same rename pattern
   - Or if normalized matching is used, might find the wrong experiment

**Result:** ❌ Unpredictable behavior, potentially renames wrong experiment

## Why This Happens

1. **Sequential Processing:** Rows are processed one-by-one in order
2. **Immediate Updates:** Each rename updates `experiment_id` immediately (within transaction)
3. **Unique Constraint:** `experiment_id` must be unique across all experiments
4. **Name Reuse:** Later rows see the new IDs from earlier renames

## The Rule

**Process "source" renames before "target" renames:**

In your case:
- `HPHT_MH_036-2` must become `_Desorption` (source)
- Before `HPHT_MH_036-5` becomes `-2` (target)

Think of it as: "Free up the name before someone else uses it"

## How to Verify Your Order

### Visual Check

Draw arrows from old → new:
```
036-2 -----> 036_Desorption
036-5 -----> 036-2
```

If arrow A's target is arrow B's source, then A must come first.

### Algorithm

1. List all (old_id, new_id) pairs
2. For each pair, check if new_id appears as old_id in another pair
3. If yes, that other pair must come AFTER this one
4. Sort accordingly

## Recommendation for Your Scenario

**Use the order you provided:**

```excel
| experiment_id            | old_experiment_id | overwrite | status  |
|--------------------------|-------------------|-----------|---------|
| HPHT_MH_036              | HPHT_MH_036       | TRUE      | ONGOING |
| HPHT_MH_036_Desorption   | HPHT_MH_036-2     | TRUE      | ONGOING |
| HPHT_MH_036-2            | HPHT_MH_036-5     | TRUE      | ONGOING |
```

This is the correct order and will work perfectly.

## Testing

Run the test suite to verify:
```bash
pytest tests/test_experiment_rename.py::TestChainRenames::test_chain_rename_correct_order -v
```

This test uses your exact scenario and verifies it works correctly.

## Summary

- ✅ Your scenario WILL work with the order shown
- ⚠️ Order is CRITICAL for chain renames
- 📝 See `docs/EXPERIMENT_RENAME_GUIDE.md` for complete documentation
- 🧪 Test suite validates the behavior
- 🔄 All relationships (results, notes, etc.) are preserved

