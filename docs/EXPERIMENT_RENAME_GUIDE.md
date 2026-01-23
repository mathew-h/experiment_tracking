# Experiment Rename Guide

## Overview

The bulk upload system supports renaming experiments using the `old_experiment_id` column. This allows you to fix experiment ID naming conventions while preserving all relationships (results, notes, conditions, additives).

## How It Works

When you provide both `experiment_id` (new name) and `old_experiment_id` (current name) with `overwrite=True`:

1. System finds the experiment by `old_experiment_id`
2. Updates `experiment_id` to the new value
3. Recalculates lineage fields (`base_experiment_id`, `parent_experiment_fk`)
4. Updates denormalized `experiment_id` in related tables (notes, modifications log)
5. All relationships remain intact (results linked via integer FK)

## Basic Usage

### Simple Rename

```excel
| experiment_id          | old_experiment_id | overwrite | status   |
|------------------------|-------------------|-----------|----------|
| HPHT_MH_036_Desorption | HPHT_MH_036-2     | TRUE      | ONGOING  |
```

This renames `HPHT_MH_036-2` to `HPHT_MH_036_Desorption`.

### No Rename (Update Only)

```excel
| experiment_id   | old_experiment_id | overwrite | status    |
|-----------------|-------------------|-----------|-----------|
| HPHT_MH_036     |                   | TRUE      | COMPLETED |
```

Updates experiment without renaming (leave `old_experiment_id` blank).

## Chain Renames (IMPORTANT)

### The Problem

When multiple renames create a dependency chain (new ID of one experiment = old ID of another), **processing order matters**:

```
HPHT_MH_036-2 -> HPHT_MH_036_Desorption  (frees up "-2")
HPHT_MH_036-5 -> HPHT_MH_036-2           (uses freed "-2")
```

### ✅ CORRECT Order

Process in dependency order (rename away from conflicting names first):

```excel
| experiment_id            | old_experiment_id | overwrite | status  |
|--------------------------|-------------------|-----------|---------|
| HPHT_MH_036_Desorption   | HPHT_MH_036-2     | TRUE      | ONGOING |
| HPHT_MH_036-2            | HPHT_MH_036-5     | TRUE      | ONGOING |
```

**Why it works:**
1. Row 1: `HPHT_MH_036-2` → `HPHT_MH_036_Desorption` (ID `-2` is now free)
2. Row 2: `HPHT_MH_036-5` → `HPHT_MH_036-2` (uses the freed ID)

### ❌ WRONG Order

```excel
| experiment_id            | old_experiment_id | overwrite | status  |
|--------------------------|-------------------|-----------|---------|
| HPHT_MH_036-2            | HPHT_MH_036-5     | TRUE      | ONGOING |
| HPHT_MH_036_Desorption   | HPHT_MH_036-2     | TRUE      | ONGOING |
```

**Why it fails:**
1. Row 1: `HPHT_MH_036-5` → `HPHT_MH_036-2` (succeeds)
2. Row 2: Looks for experiment with ID `HPHT_MH_036-2` to rename
   - But that ID now belongs to the renamed experiment from row 1 (wrong experiment!)
   - Or if the original `-2` was already renamed, it won't be found

## How to Determine Correct Order

### Rule of Thumb
**Rename away from conflicting names before renaming into them.**

### Visualization

Think of it like musical chairs:
1. Someone must leave a chair before someone else can sit in it
2. Process "leaving" renames before "entering" renames

### Complex Example

Your scenario:
```
HPHT_MH_036     -> HPHT_MH_036     (no change)
HPHT_MH_036-2   -> HPHT_MH_036_Desorption
HPHT_MH_036-5   -> HPHT_MH_036-2
```

**Dependency Graph:**
- `-2` must rename to `_Desorption` before `-5` can rename to `-2`
- `036` has no dependency (no change)

**Correct order:**
1. `HPHT_MH_036` (no change - can go anywhere)
2. `HPHT_MH_036-2 → HPHT_MH_036_Desorption` (must go before #3)
3. `HPHT_MH_036-5 → HPHT_MH_036-2` (must go after #2)

## Best Practices

### 1. Plan Your Renames
List all renames first, identify dependencies, order accordingly.

### 2. Use a Spreadsheet Helper
Create a column showing dependencies:
```excel
| old_id        | new_id            | depends_on  | order |
|---------------|-------------------|-------------|-------|
| HPHT_MH_036-2 | HPHT_MH_036_Des   | none        | 1     |
| HPHT_MH_036-5 | HPHT_MH_036-2     | row 1       | 2     |
```

### 3. Process in Batches
If order is complex, split into multiple uploads:
- Batch 1: Rename experiments to temporary unique names
- Batch 2: Rename from temporary to final names

### 4. Verify Before Upload
Check that no new ID appears as an old ID in subsequent rows (unless that row processes first).

### 5. Test with Small Batches
Test complex renames with a few experiments first.

## Technical Details

### Why Order Matters

- Bulk upload processes rows **sequentially** in Excel sheet order
- Each rename immediately updates the database (within transaction)
- Unique constraint on `experiment_id` is enforced
- Later rows see the results of earlier renames

### What Gets Updated

When renaming an experiment:
- ✅ `experiment_id` (primary string identifier)
- ✅ `base_experiment_id` (recalculated from new ID)
- ✅ `parent_experiment_fk` (recalculated from new ID)
- ✅ `ExperimentNotes.experiment_id` (denormalized field)
- ✅ `ModificationsLog.experiment_id` (denormalized field)
- ✅ `ExperimentalConditions.experiment_id` (denormalized field)
- ✅ Results, samples, conditions remain linked (use integer FKs)

### Transaction Safety

All renames in one upload happen in a **single transaction**:
- If any rename fails, entire batch rolls back
- Database remains consistent
- No partial updates

## Troubleshooting

### Error: "old_experiment_id 'XXX' not found"

**Cause:** The experiment you're trying to rename doesn't exist (or was already renamed by an earlier row).

**Fix:** 
- Verify the old ID exists in your database
- Check if an earlier row in your sheet already renamed it
- Reorder rows if needed

### Error: "experiment_id 'XXX' already exists"

**Cause:** Trying to rename to an ID that already exists.

**Fix:**
- Check for duplicate new IDs in your sheet
- Reorder rows if this is a chain rename scenario
- Ensure the target ID is freed before using it

### Unexpected Results After Rename

**Symptoms:** Wrong experiment was renamed, or lineage looks wrong.

**Cause:** Rows processed in wrong order.

**Fix:**
- Review dependencies between renames
- Reorder rows in Excel sheet
- Re-upload with correct order

## Example Scripts

See `tests/test_experiment_rename.py` for comprehensive examples:
- Simple renames
- Chain renames (correct and wrong order)
- Verification that relationships are preserved
- Edge cases and error conditions

## Summary

✅ **DO:**
- Use `old_experiment_id` with `overwrite=True`
- Order rows to avoid conflicts
- Test complex renames in stages
- Verify results after upload

❌ **DON'T:**
- Assume rows can be in any order
- Forget to set `overwrite=True`
- Rename to an ID that still exists
- Skip testing with small batches first

