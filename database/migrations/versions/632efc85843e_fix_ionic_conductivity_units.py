"""fix ionic conductivity units

Revision ID: 632efc85843e
Revises: 1e2ca98f0dfe
Create Date: 2026-02-04 09:28:17.840582

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '632efc85843e'
down_revision: Union[str, None] = '1e2ca98f0dfe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - SQLite compatible and idempotent."""
    from alembic import context
    from sqlalchemy import inspect
    
    conn = context.get_context().bind
    inspector = inspect(conn)
    all_tables = inspector.get_table_names()

    # 0. CRITICAL: Clean up temp tables from failed migrations
    temp_table = '_alembic_tmp_elemental_analysis'
    if temp_table in all_tables:
        op.drop_table(temp_table)

    # 1. Update elemental_analysis: make external_analysis_id NOT NULL
    # Using batch mode for ALTER COLUMN logic (changing nullability)
    with op.batch_alter_table('elemental_analysis', schema=None) as batch_op:
        batch_op.alter_column('external_analysis_id',
               existing_type=sa.INTEGER(),
               nullable=False)

    # 2. Update experiments: remove/add FK for parent_experiment_fk
    # Skip self-referential FK constraint in SQLite to avoid circular dependency
    # But if we were adding a column, we'd do it here. 
    # Since the autogen suggested create_foreign_key, we check if it's needed or if we should skip.
    # The rule says: "For self-referential FKs, always skip the constraint"
    # Autogen: op.create_foreign_key(None, 'experiments', 'experiments', ['parent_experiment_fk'], ['id'], ondelete='SET NULL')
    # We will SKIP adding this constraint in SQLite.
    
    # 3. Update external_analyses: drop FK to pxrf_readings
    # Autogen: op.drop_constraint(None, 'external_analyses', type_='foreignkey')
    # We need to find the name of the constraint to drop it properly, or rely on naming convention if it was named.
    # Since SQLite doesn't really support dropping unnamed constraints easily without recreating table, batch mode handles it.
    
    with op.batch_alter_table('external_analyses', schema=None) as batch_op:
        # Finding the constraint to drop is tricky if unnamed. 
        # Ideally we inspect constraints.
        # However, typically we just recreate the table in batch mode without the constraint.
        # If we don't know the name, we can try to inspect or just ignore if it's not strictly enforced by SQLite in legacy mode.
        # But assuming we want to clean up the schema definition:
        
        # Get existing FKs to identify the one to drop (referencing pxrf_readings)
        fks = inspector.get_foreign_keys('external_analyses')
        for fk in fks:
            if fk['referred_table'] == 'pxrf_readings':
                batch_op.drop_constraint(fk['name'], type_='foreignkey')


def downgrade() -> None:
    """Downgrade schema - SQLite compatible and idempotent."""
    from alembic import context
    from sqlalchemy import inspect
    
    conn = context.get_context().bind
    inspector = inspect(conn)
    
    # 1. Re-add FK to external_analyses
    with op.batch_alter_table('external_analyses', schema=None) as batch_op:
        # Re-add FK to pxrf_readings if it doesn't exist
        # Note: referencing specific column reading_no
        fks = inspector.get_foreign_keys('external_analyses')
        has_fk = any(fk['referred_table'] == 'pxrf_readings' for fk in fks)
        if not has_fk:
            batch_op.create_foreign_key('fk_external_analyses_pxrf', 'pxrf_readings', ['pxrf_reading_no'], ['reading_no'], ondelete='SET NULL')

    # 2. Drop parent_experiment_fk FK in experiments (if it existed)
    # Since we skipped creating it in upgrade, we technically don't need to drop it here for SQLite correctness,
    # but if it existed previously we might want to restore it? 
    # The autogen dropped it in upgrade (implied by "op.create_foreign_key" usually means it was missing or being modified).
    # Wait, autogen said "op.create_foreign_key" in UPGRADE, meaning it wants to ADD it.
    # So in DOWNGRADE we should DROP it.
    # But since we SKIPPED adding it in upgrade (due to circular dep rule), we don't need to drop it here.
    
    # 3. Revert elemental_analysis nullability
    with op.batch_alter_table('elemental_analysis', schema=None) as batch_op:
        batch_op.alter_column('external_analysis_id',
               existing_type=sa.INTEGER(),
               nullable=True)
