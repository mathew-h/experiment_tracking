"""add_experiment_number_field

Revision ID: add_experiment_number
Create Date: 2023-03-19

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision: str = 'add_experiment_number'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to add experiment_number field."""
    # Step 1: Add the column as nullable first
    op.add_column('experiments', sa.Column('experiment_number', sa.Integer(), nullable=True))
    
    # Step 2: Create a function to update existing experiments with sequential numbers
    connection = op.get_bind()
    
    # Get all experiment IDs ordered by creation date
    result = connection.execute(
        text("SELECT id FROM experiments ORDER BY created_at ASC")
    ).fetchall()
    
    # Assign sequential numbers to existing experiments
    for index, (experiment_id,) in enumerate(result, start=1):
        connection.execute(
            text("UPDATE experiments SET experiment_number = :number WHERE id = :id"),
            {"number": index, "id": experiment_id}
        )
    
    # Step 3: Make the column non-nullable and unique
    op.alter_column('experiments', 'experiment_number', nullable=False)
    op.create_unique_constraint('uq_experiment_number', 'experiments', ['experiment_number'])


def downgrade() -> None:
    """Downgrade schema to remove experiment_number field."""
    # Remove the unique constraint first
    op.drop_constraint('uq_experiment_number', 'experiments', type_='unique')
    
    # Then drop the column
    op.drop_column('experiments', 'experiment_number')