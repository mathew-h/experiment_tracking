# Data Migrations

This directory contains data migration scripts for updating existing data in the database.

## Available Migrations

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