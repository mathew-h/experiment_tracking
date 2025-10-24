#!/usr/bin/env python3
"""
Script to run data migrations for the experiment tracking system.

Usage:
    python scripts/run_data_migration.py <migration_name>

Available migrations:
    - calculate_grams_per_ton_yield_004: Calculate grams_per_ton_yield for all existing ScalarResults (legacy)
    - recalculate_yields_002: Recalculate all yield values (legacy)
    - recalculate_derived_conditions_001: Recalculate derived experimental conditions (legacy)
    - update_catalyst_ppm_rounding_003: Update catalyst PPM rounding (legacy)
    - recompute_calculated_fields_005: Unified recalculation for conditions, additives, and scalar results
"""

import sys
import os
import importlib.util

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def run_migration(migration_name):
    """Run a specific data migration by name."""
    migration_path = os.path.join(project_root, 'database', 'data_migrations', f'{migration_name}.py')
    
    if not os.path.exists(migration_path):
        print(f"Error: Migration file '{migration_path}' not found.")
        return False
    
    try:
        # Import and run the migration
        spec = importlib.util.spec_from_file_location(migration_name, migration_path)
        migration_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration_module)
        
        # Run the migration
        migration_module.run_migration()
        return True
        
    except Exception as e:
        print(f"Error running migration '{migration_name}': {e}")
        return False

def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    
    migration_name = sys.argv[1]
    
    # Available migrations
    available_migrations = [
        'calculate_grams_per_ton_yield_004',
        'recalculate_yields_002', 
        'recalculate_derived_conditions_001',
        'update_catalyst_ppm_rounding_003',
        'chemical_migration',
        'recompute_calculated_fields_005'
    ]
    
    if migration_name not in available_migrations:
        print(f"Error: Unknown migration '{migration_name}'")
        print(f"Available migrations: {', '.join(available_migrations)}")
        sys.exit(1)
    
    print(f"Running migration: {migration_name}")
    success = run_migration(migration_name)
    
    if success:
        print(f"Migration '{migration_name}' completed successfully.")
    else:
        print(f"Migration '{migration_name}' failed.")
        sys.exit(1)

if __name__ == "__main__":
    main() 