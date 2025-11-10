# PowerBI Relationship Configuration Guide

## Database Schema Summary

### Experiments Table (Primary)
- `id` (Integer, PK) - Auto-incrementing primary key
- `experiment_id` (String, Unique) - Human-readable ID (e.g., "HPHT_JW_005")
- `experiment_number` (Integer, Unique) - Sequential experiment number
- `base_experiment_id` (String) - Base experiment for derivations
- `parent_experiment_fk` (Integer, FK → experiments.id) - Parent experiment reference
- `sample_id` (String, FK → sample_info.sample_id)
- `researcher`, `date`, `status`, etc.

### Experimental Conditions Table (Child)
- `id` (Integer, PK)
- `experiment_id` (String) - Denormalized copy (NOT a primary identifier)
- `experiment_fk` (Integer, FK → experiments.id) - Foreign key to experiments
- Various condition fields...

### Other Related Tables
- `experiment_notes` - Links via `experiment_fk` → `experiments.id`
- `modifications_log` - Links via `experiment_fk` → `experiments.id`
- `experimental_results` - Links via `experiment_fk` → `experiments.id`
- `sample_info` - Links via `sample_id` (String key)

---

## PowerBI Relationship Configuration

### 1. Core Relationships (One-to-Many)

#### Experiment → Experimental Conditions
```
experiments[id] (1) → (*) experimental_conditions[experiment_fk]
Direction: Single (experiments filters conditions)
Cross-filter: Single direction
```

#### Experiment → Notes
```
experiments[id] (1) → (*) experiment_notes[experiment_fk]
Direction: Single (experiments filters notes)
Cross-filter: Single direction
```

#### Experiment → Results
```
experiments[id] (1) → (*) experimental_results[experiment_fk]
Direction: Single (experiments filters results)
Cross-filter: Single direction
```

#### Sample → Experiments
```
sample_info[sample_id] (1) → (*) experiments[sample_id]
Direction: Both (optional, depends on your needs)
```

---

### 2. Lineage Relationships (Self-Referencing)

#### Option A: Using Parent FK (Recommended)
Create a **duplicate table reference** in PowerBI called `experiments_parent`:

```
experiments[id] (1) → (*) experiments_parent[parent_experiment_fk]
Direction: Single
Cross-filter: Single direction
Make this relationship INACTIVE by default
```

Then use DAX measures to activate it when needed:
```dax
Parent Experiment ID = 
CALCULATE(
    SELECTEDVALUE(experiments[experiment_id]),
    USERELATIONSHIP(experiments[id], experiments_parent[parent_experiment_fk])
)

Child Experiments = 
CALCULATE(
    COUNTROWS(experiments),
    USERELATIONSHIP(experiments[id], experiments_parent[parent_experiment_fk])
)
```

#### Option B: Using Base Experiment ID (Simpler for Hierarchies)
Don't create a relationship. Instead, use DAX measures:

```dax
// Get all child experiments for selected experiment
Child Experiments = 
VAR SelectedExpID = SELECTEDVALUE(experiments[experiment_id])
RETURN
CALCULATE(
    COUNTROWS(experiments),
    FILTER(
        ALL(experiments),
        experiments[base_experiment_id] = SelectedExpID &&
        experiments[experiment_id] <> SelectedExpID
    )
)

// List of child experiment IDs
Child Experiment List = 
VAR SelectedExpID = SELECTEDVALUE(experiments[experiment_id])
RETURN
CONCATENATEX(
    FILTER(
        ALL(experiments),
        experiments[base_experiment_id] = SelectedExpID &&
        experiments[experiment_id] <> SelectedExpID
    ),
    experiments[experiment_id],
    ", ",
    experiments[experiment_id], ASC
)

// Get parent experiment
Parent Experiment = 
VAR CurrentBaseID = SELECTEDVALUE(experiments[base_experiment_id])
VAR CurrentExpID = SELECTEDVALUE(experiments[experiment_id])
RETURN
IF(
    CurrentBaseID <> CurrentExpID,
    CurrentBaseID,
    BLANK()
)

// Check if experiment is a derivation
Is Derivation = 
VAR CurrentBaseID = SELECTEDVALUE(experiments[base_experiment_id])
VAR CurrentExpID = SELECTEDVALUE(experiments[experiment_id])
RETURN
IF(CurrentBaseID <> CurrentExpID, "Yes", "No")
```

---

## Common Mistakes to Avoid

### ❌ WRONG: Using experiment_id from experimental_conditions
```
experiments[base_experiment_id] (?) → (?) experimental_conditions[experiment_id]
```
**Problem:** This creates a many-to-many relationship that causes incorrect filtering.
**Why:** `experimental_conditions.experiment_id` is not a unique identifier.

### ❌ WRONG: Creating bidirectional filter on parent relationship
```
experiments[id] ← → experiments[parent_experiment_fk]
```
**Problem:** Circular filtering and ambiguous filter propagation.

### ❌ WRONG: Using experiment_id for lineage
```
experiments[experiment_id] (?) → (?) experiments[base_experiment_id]
```
**Problem:** String matching can be unreliable with variations in formatting.
**Solution:** Use `parent_experiment_fk → id` (integer FK) or DAX measures.

---

## Recommended Approach for Lineage Queries

### For Filtering by Parent/Base Experiment
Use a **Table visual** or **Matrix visual** with DAX measures:

```dax
// Create a hierarchy measure
Experiment Hierarchy = 
VAR CurrentExpID = SELECTEDVALUE(experiments[experiment_id])
VAR BaseID = SELECTEDVALUE(experiments[base_experiment_id])
VAR IsBase = (CurrentExpID = BaseID)
RETURN
IF(
    IsBase,
    CurrentExpID,
    BaseID & " → " & CurrentExpID
)

// Count direct children only
Direct Children Count = 
VAR SelectedExpID = SELECTEDVALUE(experiments[experiment_id])
RETURN
CALCULATE(
    COUNTROWS(experiments),
    FILTER(
        ALL(experiments),
        experiments[base_experiment_id] = SelectedExpID &&
        experiments[experiment_id] <> SelectedExpID
    )
)

// Count all descendants (including grandchildren)
All Descendants Count = 
VAR SelectedExpBaseID = SELECTEDVALUE(experiments[base_experiment_id])
RETURN
CALCULATE(
    COUNTROWS(experiments),
    FILTER(
        ALL(experiments),
        experiments[base_experiment_id] = SelectedExpBaseID &&
        experiments[experiment_id] <> SelectedExpBaseID
    )
)
```

### For Visualizing Lineage Tree
Create a calculated column in experiments table:

```dax
Lineage Level = 
VAR CurrentExpID = experiments[experiment_id]
VAR BaseID = experiments[base_experiment_id]
VAR HasParent = experiments[parent_experiment_fk]
RETURN
SWITCH(
    TRUE(),
    CurrentExpID = BaseID && ISBLANK(HasParent), 0,  // Base experiment
    NOT(ISBLANK(HasParent)), 1,  // Direct child
    1  // Default to child level
)
```

---

## Testing Your PowerBI Setup

Run these checks to verify correct configuration:

1. **Filter to HPHT_JW_005**
   - Expected children: HPHT_JW_005-2, HPHT_JW_005-3, HPHT_JW_005-4, HPHT_JW_005-3_Desorption
   - Should NOT show: OTHER_MH_001, CF-05-1

2. **Check CF-05-1**
   - Base experiment: CF-05
   - Parent: CF-05 (not HPHT_JW_005)

3. **Verify relationship paths**
   - All experiment metadata should come from `experiments` table
   - All conditions should come through the `experiment_fk` relationship
   - Never filter experiments by `experimental_conditions.experiment_id`

---

## Quick Fix for Your Current Issue

If you currently have a relationship like:
```
experiments[base_experiment_id] → experimental_conditions[experiment_id]
```

**Delete this relationship** and replace it with:
```
experiments[id] (1) → (*) experimental_conditions[experiment_fk]
```

Then use DAX measures (shown above) for lineage queries instead of relationships.

---

## Summary

**Always use:**
- `experiments.experiment_id` for display
- `experiments.id` and `experiments.parent_experiment_fk` for relationships
- `experiments.base_experiment_id` for filtering children (via DAX, not relationships)

**Never use:**
- `experimental_conditions.experiment_id` for relationships or filtering
- Direct string matching between lineage fields (use integer FKs or DAX)

