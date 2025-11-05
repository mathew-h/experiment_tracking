# Data Migrations

This directory contains data migration scripts for updating existing data in the database.

## Available Migrations

### normalize_pxrf_reading_numbers_008.py
**Purpose**: Fix float formatting issue where reading numbers are stored as "1.0", "2.0", "34.0" instead of "1", "2", "34".

**What it does**:
- Normalizes all `reading_no` values in `pxrf_readings` table (removes `.0` suffix)
- Normalizes all `pxrf_reading_no` values in `external_analyses` table
- Handles comma-separated values (e.g., "2.0,3.0,4.0" → "2,3,4")
- Makes matching work correctly in Power BI and other tools

**When to run**: After discovering that pXRF data and sample analyses aren't matching due to float formatting (e.g., "34" vs "34.0").

**Usage**:
```bash
# Preview changes (dry run)
python database/data_migrations/normalize_pxrf_reading_numbers_008.py

# Apply normalization
python database/data_migrations/normalize_pxrf_reading_numbers_008.py --apply
```

**Why this happens**: Excel stores all numbers as floats internally. When pandas reads integer columns, it converts them to float (1 → 1.0), then string conversion produces "1.0" instead of "1".

**Example**: 
- Before: `reading_no = "1.0"`, `pxrf_reading_no = "34.0"` → No match ❌
- After: `reading_no = "1"`, `pxrf_reading_no = "34"` → Match! ✅

### backfill_pxrf_readings_009.py
**Purpose**: Ensure every ExternalAnalysis pXRF entry references a valid row in the `pxrf_readings` table.

**What it does**:
- Scans all `ExternalAnalysis` rows of type `pXRF`
- Removes legacy pXRF analysis rows whose `pxrf_reading_no` is blank/NULL
- Normalizes comma-separated reading numbers and ensures they exist in `pxrf_readings`
- Renames existing readings when safe or creates placeholder rows when missing
- Writes the normalized reading list back to `pxrf_reading_no`

**When to run**: After importing historical pXRF analyses or discovering analyses referencing readings that do not exist in the `pxrf_readings` table.

**Usage**:
```bash
# Preview changes (dry run)
python database/data_migrations/backfill_pxrf_readings_009.py

# Apply changes
python database/data_migrations/backfill_pxrf_readings_009.py --apply
```

### split_pxrf_external_analyses_010.py
**Purpose**: Convert pXRF ExternalAnalysis rows that contain multiple reading numbers into one row per reading.

**What it does**:
- Normalizes `pxrf_reading_no` values
- Removes legacy pXRF analysis rows with empty/NULL readings
- Splits comma-separated lists into distinct ExternalAnalysis rows (one per reading)
- Copies metadata (date, laboratory, analyst, description, metadata) to each new row
- Skips creation when a per-reading entry already exists to avoid duplicates

**When to run**: After running `backfill_pxrf_readings_009.py`, or whenever comma-separated pXRF readings appear in ExternalAnalysis records.

**Usage**:
```bash
# Preview changes (dry run)
python database/data_migrations/split_pxrf_external_analyses_010.py

# Apply changes
python database/data_migrations/split_pxrf_external_analyses_010.py --apply
```

### merge_duplicate_samples_007.py
**Purpose**: Identify and merge duplicate sample IDs that differ only in formatting (e.g., "rock-001", "ROCK-001", "rock 001").

**What it does**:
- Finds groups of samples with IDs that normalize to the same value (ignoring case, hyphens, underscores, spaces)
- Chooses the best sample to keep as primary (prefers canonical format: UPPERCASE, no spaces/underscores)
- Merges metadata from duplicate samples (keeps non-null values)
- Migrates all foreign key references (experiments, external analyses, photos, elemental results)
- Removes duplicate entries intelligently (avoids constraint violations)
- Deletes duplicate sample records

**When to run**: After deploying the fixed `rock_inventory.py` that prevents future duplicates. Run in dry-run mode first to preview changes.

**Usage**:
```bash
# Step 1: Identify duplicates (no changes)
python database/data_migrations/identify_duplicate_samples.py

# Step 2: Preview merge (dry run, no changes)
python database/data_migrations/merge_duplicate_samples_007.py

# Step 3: Apply merge (makes changes)
python database/data_migrations/merge_duplicate_samples_007.py --apply
```

**Example**: Samples "rock-001", "ROCK-001", "rock 001" will be merged into a single "ROCK-001" sample.

### identify_duplicate_samples.py
**Purpose**: Diagnostic script to identify ALL duplicate sample IDs and provide detailed analysis.

**What it shows**:
- Total samples in database vs. expected unique count
- Each duplicate group with all variants
- Character differences (case, separators, spacing)
- Foreign key reference counts for each duplicate
- Which sample will be chosen as primary in merge
- How many duplicates would be removed

**When to run**: Before running the merge script to understand what duplicates exist.

**Usage**:
```bash
python database/data_migrations/identify_duplicate_samples.py
```

**Example output**:
```
Total samples: 594
Unique samples (normalized): 547
Duplicate groups: 47
Extra duplicate records: 47

Duplicate group: '20250710-2d'
  • '20250710-2D' (has-hyphen, mixed/lowercase) [refs=5exp,2ana,1pho]
  • '20250710_2D' (has_underscore, has uppercase) [refs=2exp]
```

### Alternative Detection Methods

If Python scripts won't run, you have several options:

#### 1. Streamlit App Sidebar (Easiest)
The app sidebar now shows:
- Sample count with duplicate indicator (e.g., "594 -47 dups")
- Expandable section showing duplicate details
- Command to run merge script

#### 2. SQL Query (check_duplicates.sql)
Open `experiments.db` in SQLite Browser and run `check_duplicates.sql` to see duplicate analysis.

#### 3. PowerBI Verification
After running merge:
- Sample count should match "unique samples" count
- Duplicate entries in visualizations should disappear

See `ALTERNATIVE_DETECTION_METHODS.md` for complete details.

### check_duplicates.sql
**Purpose**: Quick script to identify and report duplicate samples without making any changes.

**What it does**:
- Scans all samples and groups by normalized ID
- Reports duplicate groups with details (references count, metadata completeness)
- Provides a summary of how many duplicates exist

**When to run**: Before running the merge script to understand the scope of the problem.

**Usage**:
```bash
python database/data_migrations/identify_duplicate_samples.py
```

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