# Data Migrations

This directory contains data migration scripts for updating existing data in the database.

## Available Migrations

### establish_experiment_lineage_006.py
**Purpose**: Establish lineage relationships for experiments with derivations (e.g., "HPHT_MH_001-2" derives from "HPHT_MH_001").

**What it does**:
- Parses all experiment IDs to identify derivations (experiments ending with "-N" where N is a number)
- Sets the `base_experiment_id` field for all derivations
- Establishes `parent_experiment_fk` relationships to link derivations to their base experiments
- Handles orphaned derivations (where the base experiment doesn't exist yet)

**When to run**: After adding the lineage tracking columns to the Experiment model. This establishes relationships for all existing experiments.

**Example**: For experiment "HPHT_MH_001-2":
- `base_experiment_id` will be set to "HPHT_MH_001"
- `parent_experiment_fk` will link to the "HPHT_MH_001" experiment (if it exists)

### calculate_grams_per_ton_yield_004.py
**Purpose**: Calculate `grams_per_ton_yield` for all existing ScalarResults entries.

**What it does**:
- Iterates through all ScalarResults entries
- Loads parent relationships (ExperimentalResults, Experiment, ExperimentalConditions)
- Calls the `calculate_yields()` method to calculate `grams_per_ton_yield`
- Uses the formula: `grams_per_ton_yield = 1,000,000 * (ammonia_mass_g / rock_mass)`
- Where `ammonia_mass_g = (solution_ammonium_concentration / 1000) * (water_volume / 1000) * 18.04`

**When to run**: After adding the automatic calculation logic to ensure all existing data has calculated yields.

### recalculate_yields_002.py
**Purpose**: Recalculate all yield values using the latest calculation logic.

### recalculate_derived_conditions_001.py
**Purpose**: Recalculate derived experimental conditions.

### update_catalyst_ppm_rounding_003.py
**Purpose**: Update catalyst PPM rounding for consistency.

## Running Migrations

### Option 1: Using the runner script (Recommended)
```bash
python scripts/run_data_migration.py calculate_grams_per_ton_yield_004
```

### Option 2: Running directly
```bash
python database/data_migrations/calculate_grams_per_ton_yield_004.py
```

## Migration Safety

- All migrations include error handling and rollback functionality
- Migrations log their progress and provide detailed output
- Always backup your database before running migrations
- Test migrations on a copy of your data first

## Automatic Calculation

After running the migration, new experimental results will automatically calculate `grams_per_ton_yield` when:
- `solution_ammonium_concentration` is provided
- The parent experiment has valid `rock_mass` and `water_volume` values
- The calculation is performed in the `_save_or_update_scalar` function in `experimental_results.py` 